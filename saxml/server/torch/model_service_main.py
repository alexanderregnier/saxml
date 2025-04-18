# Copyright 2022 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""The main module of model services."""

import json
import re
from typing import Optional, Sequence

from absl import app
from absl import flags
from absl import logging
import grpc
from saxml.protobuf import modelet_pb2
from saxml.protobuf import modelet_pb2_grpc
from saxml.server import model_service_base
from saxml.server import servable_model_registry
from saxml.server import spmd_backend
from saxml.server.torch import vllm_params  # pylint: disable=unused-import

_SAX_CELL = flags.DEFINE_string(
    'sax_cell',
    None,
    'Optional SAX cell of the admin server. If set, heartbeat is enabled.',
)
_MODEL_FILTER_REGEX = flags.DEFINE_string(
    'model_filter_regex',
    None,
    'A regex to filter (full match) models in the registry by their names.',
)
_ADMIN_PORT = flags.DEFINE_integer(
    'admin_port', None, 'Optional port for the built-in admin server.'
)

_PORT = flags.DEFINE_integer(
    'port', None, 'Port for the RPC service.', required=True
)
_PLATFORM_CHIP = flags.DEFINE_string(
    'platform_chip', 'cpu', 'Optional chip name.'
)
_PLATFORM_TOPOLOGY = flags.DEFINE_string(
    'platform_topology', '1', 'Optional topology description.'
)
_TAGS = flags.DEFINE_list('tags', [], 'Optional list of string tags.')

# Internal tuning knobs. Consult sax-dev@ before tweaking these.
_MODELS = flags.DEFINE_list(
    'models', [], 'Optional model paths to load at startup time.'
)
_MODEL_KEYS = flags.DEFINE_list(
    'model_keys', [], 'Optional keys to identify loaded models at startup time.'
)
_CHECKPOINTS = flags.DEFINE_list(
    'checkpoints', [], 'Optional model checkpoints to load at startup time.'
)
_MODEL_CONFIG_OVERRIDES = flags.DEFINE_list(
    'model_config_overrides',
    [],
    'Optional model config overrides for the models loaded at startup time. The'
    ' format is comma-separated JSON for each model. For example:'
    ' \'{"BATCH_SIZE": 4, "BATCH_WAIT_SECS": 30},{"NUM_SAMPLES": 4}\'',
)
_DETERMINISTIC_RNG = flags.DEFINE_bool(
    'deterministic_rng',
    False,
    'Whether to use a fixed RNG seed for all models.',
)
_HOST_ORDINAL = flags.DEFINE_integer(
    'host_ordinal',
    None,
    (
        'Ordinal of the current host in a multi-host setup. Host 0 is the'
        ' worker server that handles requests, and others will run the'
        ' secondary worker loop.'
    ),
)
_EARLY_REJECT_ON_DORMANT = flags.DEFINE_bool(
    'early_reject_on_dormant',
    False,
    'If true, reject incoming model service requests early when the model'
    ' server is dormant.',
)
_KEEP_STATICALLY_LOADED_MODELS = flags.DEFINE_bool(
    'keep_statically_loaded_models',
    False,
    'If true, the server will keep statically configured models specified in'
    ' --model_keys and decline admin server requests to load new models or'
    ' update existing models. Must be used in conjunction with --model_keys.',
)


@flags.multi_flags_validator(
    ['models', 'model_keys', 'checkpoints', 'model_config_overrides'],
    message='models, model_keys, and checkpoints must have the same length',
)
def _check_model_checkpoint_flags(flags_dict):
  return len(flags_dict['models']) == len(flags_dict['checkpoints']) and (
      len(flags_dict['models']) == len(flags_dict['model_keys'])
      and (
          not flags_dict['model_config_overrides']
          or len(flags_dict['models'])
          == len(flags_dict['model_config_overrides'])
      )
  )


def _load_static_model(
    port,
    model: str,
    model_key: str,
    checkpoint: str,
    model_config_overrides: dict[str, str],
    channel_creds: Optional[grpc.ChannelCredentials],
) -> None:
  """Loads statically specified model to a started service."""
  logging.info(
      'Loading key %s, model %s, checkpoint %s.', model_key, model, checkpoint
  )
  if channel_creds is None:
    channel = grpc.insecure_channel(f'localhost:{port}')
  else:
    channel = grpc.secure_channel(f'localhost:{port}', channel_creds)
  with channel:
    grpc.channel_ready_future(channel).result(timeout=10)
    stub = modelet_pb2_grpc.ModeletStub(channel)
    req = modelet_pb2.LoadRequest(
        model_key=model_key,
        model_path=model,
        checkpoint_path=checkpoint,
        overrides=model_config_overrides,
    )
    try:
      stub.Load(req)
    except grpc.RpcError as e:
      logging.exception('Exception during loading: %s', e)
      raise e


def run(channel_creds: Optional[grpc.ChannelCredentials]) -> None:
  """Runs the server until it is stopped."""
  if _MODEL_FILTER_REGEX.value is not None:
    logging.info('Setting model filter to %s', _MODEL_FILTER_REGEX.value)
    servable_model_registry.MODEL_FILTER_REGEX = re.compile(
        _MODEL_FILTER_REGEX.value
    )
  if _KEEP_STATICALLY_LOADED_MODELS.value and not _MODEL_KEYS.value:
    assert (
        _MODEL_KEYS.value
    ), '--keep_statically_loaded_models requires --model_keys to be set.'
  seed = 1234 if _DETERMINISTIC_RNG.value else None
  is_primary = _HOST_ORDINAL.value is None or _HOST_ORDINAL.value == 0
  spmd_bknd = spmd_backend.SingleHostBackend()

  runner = model_service_base.ModelServicesRunner(
      is_primary_process=is_primary,
      port=_PORT.value,
      deterministic_prng_seed=seed,
      sax_cell=_SAX_CELL.value,
      admin_port=_ADMIN_PORT.value,
      platform_chip=_PLATFORM_CHIP.value,
      platform_topology=_PLATFORM_TOPOLOGY.value,
      tags=_TAGS.value,
      backend=spmd_bknd,
      early_reject_on_dormant=_EARLY_REJECT_ON_DORMANT.value,
      keep_statically_loaded_models=_KEEP_STATICALLY_LOADED_MODELS.value,
  )
  try:
    runner.start()
    if is_primary:
      model_config_overrides: list[dict[str, str]] = [
          {key: str(value) for key, value in json.loads(x).items()}
          for x in _MODEL_CONFIG_OVERRIDES.value
      ]
      if not model_config_overrides:
        model_config_overrides = [
            dict[str, str]() for _ in range(len(_MODELS.value))
        ]
      for model, key, ckpt, overrides in zip(
          _MODELS.value,
          _MODEL_KEYS.value,
          _CHECKPOINTS.value,
          model_config_overrides,
      ):
        _load_static_model(
            _PORT.value, model, key, ckpt, overrides, channel_creds
        )
      runner.on_initial_models_load_completion()
    runner.wait()
  finally:
    runner.stop()


def main(argv: Sequence[str]) -> None:
  del argv
  if '_import_modules' in globals():
    # pytype: disable=name-error
    # pylint: disable=undefined-variable
    _import_modules()
    # pylint: enable=undefined-variable
    # pytype: enable=name-error
  run(None)


if __name__ == '__main__':
  app.run(main)
