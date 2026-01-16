"""
Unit tests for client decorator module.
"""
import pytest
from lattice.client.core.decorator import (
    task,
    get_task_metadata,
    normalize_resources,
    TaskMetadata,
    BatchConfig,
)


class TestNormalizeResources:
    def test_none_returns_defaults(self):
        result = normalize_resources(None)
        assert result == {"cpu": 1, "cpu_mem": 0, "gpu": 0, "gpu_mem": 0}

    def test_partial_resources_merged(self):
        result = normalize_resources({"cpu": 4})
        assert result["cpu"] == 4
        assert result["cpu_mem"] == 0
        assert result["gpu"] == 0
        assert result["gpu_mem"] == 0

    def test_cpu_minimum_enforced(self):
        result = normalize_resources({"cpu": 0})
        assert result["cpu"] == 1

    def test_gpu_inferred_from_gpu_mem(self):
        result = normalize_resources({"gpu_mem": 1000})
        assert result["gpu"] == 1
        assert result["gpu_mem"] == 1000

    def test_explicit_gpu_preserved(self):
        result = normalize_resources({"gpu": 2, "gpu_mem": 4000})
        assert result["gpu"] == 2
        assert result["gpu_mem"] == 4000


class TestTaskDecorator:
    def test_basic_decoration(self):
        @task(inputs=["x"], outputs=["y"])
        def my_func(params):
            return {"y": params["x"] * 2}

        assert hasattr(my_func, "_lattice_task_metadata")
        metadata = my_func._lattice_task_metadata
        assert isinstance(metadata, TaskMetadata)
        assert metadata.func_name == "my_func"
        assert metadata.inputs == ["x"]
        assert metadata.outputs == ["y"]

    def test_with_resources(self):
        @task(inputs=["a"], outputs=["b"], resources={"cpu": 4, "gpu": 1})
        def gpu_func(params):
            return {"b": params["a"]}

        metadata = get_task_metadata(gpu_func)
        assert metadata.resources["cpu"] == 4
        assert metadata.resources["gpu"] == 1

    def test_with_data_types(self):
        @task(
            inputs=["num"],
            outputs=["result"],
            data_types={"num": "int", "result": "float"},
        )
        def typed_func(params):
            return {"result": float(params["num"])}

        metadata = get_task_metadata(typed_func)
        assert metadata.data_types["num"] == "int"
        assert metadata.data_types["result"] == "float"

    def test_code_str_captured(self):
        @task(inputs=["x"], outputs=["y"])
        def simple(params):
            return {"y": params["x"]}

        metadata = get_task_metadata(simple)
        assert "def simple(params):" in metadata.code_str
        assert 'return {"y": params["x"]}' in metadata.code_str

    def test_serialized_code_generated(self):
        @task(inputs=["x"], outputs=["y"])
        def serializable(params):
            return {"y": params["x"] + 1}

        metadata = get_task_metadata(serializable)
        assert metadata.serialized_code is not None
        assert len(metadata.serialized_code) > 0


class TestGetTaskMetadata:
    def test_decorated_function(self):
        @task(inputs=["a"], outputs=["b"])
        def decorated(params):
            return {"b": params["a"]}

        metadata = get_task_metadata(decorated)
        assert metadata.func_name == "decorated"

    def test_undecorated_function_raises(self):
        def undecorated(params):
            return params

        with pytest.raises(ValueError, match="not decorated with @task"):
            get_task_metadata(undecorated)


class TestBatchConfig:
    def test_default_batch_config(self):
        @task(inputs=["x"], outputs=["y"])
        def no_batch(params):
            return {"y": params["x"]}

        metadata = get_task_metadata(no_batch)
        assert metadata.batch_config is not None
        assert metadata.batch_config.enabled is False
        assert metadata.batch_config.batch_size == 1
        assert metadata.batch_config.batch_timeout == 0.0

    def test_batch_size_enables_batching(self):
        @task(inputs=["texts"], outputs=["embeddings"], batch_size=32)
        def embed_texts(params):
            return {"embeddings": [[0.1] * 768] * len(params["texts"])}

        metadata = get_task_metadata(embed_texts)
        assert metadata.batch_config.enabled is True
        assert metadata.batch_config.batch_size == 32
        assert metadata.batch_config.batch_timeout == 0.0

    def test_batch_size_and_timeout(self):
        @task(
            inputs=["texts"],
            outputs=["embeddings"],
            batch_size=64,
            batch_timeout=0.1,
        )
        def embed_with_timeout(params):
            return {"embeddings": [[0.1] * 768] * len(params["texts"])}

        metadata = get_task_metadata(embed_with_timeout)
        assert metadata.batch_config.enabled is True
        assert metadata.batch_config.batch_size == 64
        assert metadata.batch_config.batch_timeout == 0.1

    def test_zero_batch_size_disables_batching(self):
        @task(inputs=["x"], outputs=["y"], batch_size=0)
        def no_batch(params):
            return {"y": params["x"]}

        metadata = get_task_metadata(no_batch)
        assert metadata.batch_config.enabled is False

    def test_batch_config_to_dict(self):
        config = BatchConfig(enabled=True, batch_size=32, batch_timeout=0.1)
        data = config.to_dict()
        assert data == {
            "enabled": True,
            "batch_size": 32,
            "batch_timeout": 0.1,
        }

    def test_batch_config_from_dict(self):
        data = {"enabled": True, "batch_size": 64, "batch_timeout": 0.2}
        config = BatchConfig.from_dict(data)
        assert config.enabled is True
        assert config.batch_size == 64
        assert config.batch_timeout == 0.2
