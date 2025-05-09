load("//saxml:saxml.bzl", "py_strict_test", "pytype_strict_binary", "pytype_strict_library")
load("//saxml/server:build_defs.bzl", "create_server_binary")

licenses(["notice"])

package(
    default_visibility = ["//saxml:internal"],
)

create_server_binary(
    name = "server",
    imports_targets = [
        ":classify",
        ":detect",
        ":lm",
    ],
)

pytype_strict_binary(
    name = "vllm_server",
    srcs = [
        "model_service_main.py",
        "vllm_params.py",
    ],
    main = "model_service_main.py",
    tags = [
        # This binary is designed for external use.
        "manual",
        "nobuilder",
        "nopresubmit",
        "norapid",
        "notap",
    ],
    deps = [
        "//saxml/protobuf:modelet_py_pb2",
        "//saxml/protobuf:modelet_py_pb2_grpc",
        "//saxml/server:model_service_base",
        "//saxml/server:servable_model",
        "//saxml/server:servable_model_params",
        "//saxml/server:servable_model_registry",
        "//saxml/server:spmd_backend",
        "//saxml/server:utils",
        "//saxml/server/services:lm_service",
        "//third_party/py/absl-py:app",
        "//third_party/py/absl-py/flags",
        "//third_party/py/absl-py/logging",
        "//third_party/py/grpcio",
        "//third_party/py/numpy",
        "//third_party/py/vllm",
    ],
)

pytype_strict_library(
    name = "servable_model",
    srcs = ["servable_model.py"],
    deps = [
        "//saxml/server:servable_model",
        "//saxml/server:servable_model_params",
        "//saxml/server:utils",
        "//third_party/py/numpy",
        "//third_party/py/torch:pytorch",
    ],
)

pytype_strict_library(
    name = "classify",
    srcs = ["classify.py"],
    deps = [
        ":servable_model",
        "//saxml/server:servable_model_registry",
        "//saxml/server/pax/vision:imagenet_metadata",
        "//saxml/server/services:vision_service",
        "//third_party/py/numpy",
        "//third_party/py/paxml/tasks/vision:input_generator",
        "//third_party/py/torch:pytorch",
        "//third_party/py/torchvision",
    ],
)

py_strict_test(
    name = "classify_test",
    srcs = ["classify_test.py"],
    deps = [
        ":classify",
        ":servable_model",
        "//third_party/py/absl-py/testing:absltest",
        # Unused internal protobuf deps,  # Automatically added go/proto_python_upb_flip
        "//third_party/py/praxis:py_utils",
        "//third_party/py/tensorflow:tensorflow_no_contrib",
        "//third_party/py/torchvision",
    ],
)

pytype_strict_library(
    name = "detect",
    srcs = ["detect.py"],
    deps = [
        ":servable_model",
        "//saxml/server:servable_model_registry",
        "//saxml/server/services:vision_service",
        "//third_party/py/detectron2",
        "//third_party/py/numpy",
        "//third_party/py/paxml/tasks/vision:input_generator",
        "//third_party/py/tensorflow:tensorflow_no_contrib",
        "//third_party/py/torch:pytorch",
    ],
)

py_strict_test(
    name = "detect_test",
    srcs = ["detect_test.py"],
    deps = [
        ":detect",
        ":servable_model",
        "//third_party/py/absl-py/testing:absltest",
        "//third_party/py/detectron2",
        # Unused internal protobuf deps,  # Automatically added go/proto_python_upb_flip
        "//third_party/py/praxis:py_utils",
        "//third_party/py/tensorflow:tensorflow_no_contrib",
    ],
)

pytype_strict_library(
    name = "lm",
    srcs = ["lm.py"],
    deps = [
        ":servable_model",
        "//saxml/protobuf:multimodal_py_pb2",
        "//saxml/server:servable_model_registry",
        "//saxml/server/services:lm_service",
        "//saxml/server/services:multimodal_service",
        "//third_party/py/torch:pytorch",
    ],
)

filegroup(
    name = "testdata",
    testonly = 1,
    srcs = glob(["testdata/*"]),
)

py_strict_test(
    name = "lm_test",
    size = "large",
    srcs = ["lm_test.py"],
    data = [
        ":testdata",
    ],
    deps = [
        ":lm",
        ":servable_model",
        "//third_party/py/absl-py/testing:absltest",
        # Unused internal protobuf deps,  # Automatically added go/proto_python_upb_flip
        "//saxml/protobuf:multimodal_py_pb2",
        "//saxml/server/services:lm_service",
        "//saxml/server/services:multimodal_service",
        "//third_party/py/tensorflow:tensorflow_no_contrib",
    ],
)
