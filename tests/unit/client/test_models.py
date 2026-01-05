"""
Unit tests for client models module.
"""
import pytest
from lattice.client.core.models import TaskOutput, TaskOutputs, LatticeTask


class TestTaskOutput:
    def test_creation(self):
        output = TaskOutput(task_id="task-1", output_key="result")
        assert output.task_id == "task-1"
        assert output.output_key == "result"

    def test_to_reference_string(self):
        output = TaskOutput(task_id="task-1", output_key="result")
        ref = output.to_reference_string()
        assert ref == "task-1.output.result"

    def test_reference_string_format(self):
        output = TaskOutput(task_id="abc-123", output_key="data")
        ref = output.to_reference_string()
        assert "abc-123" in ref
        assert "output" in ref
        assert "data" in ref


class TestTaskOutputs:
    def test_creation(self):
        outputs = TaskOutputs(task_id="task-1", output_keys=["a", "b", "c"])
        assert "a" in outputs
        assert "b" in outputs
        assert "c" in outputs

    def test_getitem(self):
        outputs = TaskOutputs(task_id="task-1", output_keys=["result"])
        output = outputs["result"]
        assert isinstance(output, TaskOutput)
        assert output.task_id == "task-1"
        assert output.output_key == "result"

    def test_getitem_missing_raises(self):
        outputs = TaskOutputs(task_id="task-1", output_keys=["a"])
        with pytest.raises(KeyError, match="not found"):
            _ = outputs["nonexistent"]

    def test_contains(self):
        outputs = TaskOutputs(task_id="task-1", output_keys=["x", "y"])
        assert "x" in outputs
        assert "z" not in outputs

    def test_keys(self):
        outputs = TaskOutputs(task_id="task-1", output_keys=["a", "b"])
        keys = outputs.keys()
        assert "a" in keys
        assert "b" in keys
        assert len(keys) == 2


class TestLatticeTask:
    def test_creation(self):
        task = LatticeTask(
            task_id="task-1",
            workflow_id="wf-1",
            server_url="http://localhost:8000",
            task_name="Test Task",
            output_keys=["result"],
        )
        assert task.task_id == "task-1"
        assert task.workflow_id == "wf-1"
        assert task.server_url == "http://localhost:8000"
        assert task.task_name == "Test Task"

    def test_outputs_accessible(self):
        task = LatticeTask(
            task_id="task-1",
            workflow_id="wf-1",
            server_url="http://localhost:8000",
            task_name="Test Task",
            output_keys=["output1", "output2"],
        )
        assert "output1" in task.outputs
        assert "output2" in task.outputs

    def test_outputs_empty_by_default(self):
        task = LatticeTask(
            task_id="task-1",
            workflow_id="wf-1",
            server_url="http://localhost:8000",
            task_name="Test Task",
        )
        assert task.outputs.keys() == []

    def test_output_reference(self):
        task = LatticeTask(
            task_id="task-1",
            workflow_id="wf-1",
            server_url="http://localhost:8000",
            task_name="Test Task",
            output_keys=["data"],
        )
        ref = task.outputs["data"].to_reference_string()
        assert ref == "task-1.output.data"
