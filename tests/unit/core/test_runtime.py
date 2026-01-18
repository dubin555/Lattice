"""
Unit tests for core/runtime module.
"""
import pytest
from dataclasses import dataclass
from typing import Dict, Any
from lattice.core.runtime.task import (
    TaskStatus,
    BaseTaskRuntime,
    CodeTaskRuntime,
    LangGraphTaskRuntime,
    TaskRuntimeRegistry,
    create_task_runtime,
)
from lattice.core.workflow.base import TaskType
from lattice.core.runtime.workflow import (
    WorkflowRuntime,
    WorkflowRuntimeManager,
)
from lattice.core.resource.node import SelectedNode


class TestCodeTaskRuntime:
    def test_creation(self):
        task = CodeTaskRuntime(
            workflow_id="wf-1",
            task_id="task-1",
            resources={"cpu": 1, "cpu_mem": 0},
            task_input={"input_params": {}},
            task_output={"output_params": {}},
            code_str="def foo(): pass",
        )
        assert task.workflow_id == "wf-1"
        assert task.task_id == "task-1"
        assert task.task_type == TaskType.CODE
        assert task.status == TaskStatus.READY

    def test_set_status(self):
        task = CodeTaskRuntime(
            workflow_id="wf-1",
            task_id="task-1",
            resources={},
        )
        task.set_status(TaskStatus.RUNNING)
        assert task.status == TaskStatus.RUNNING

    def test_set_running(self):
        task = CodeTaskRuntime(
            workflow_id="wf-1",
            task_id="task-1",
            resources={},
        )
        node = SelectedNode(node_id="node-1", node_ip="192.168.1.1")
        task.set_running(object_ref="ref-123", selected_node=node)
        
        assert task.status == TaskStatus.RUNNING
        assert task.object_ref == "ref-123"
        assert task.selected_node == node

    def test_set_completed(self):
        task = CodeTaskRuntime(
            workflow_id="wf-1",
            task_id="task-1",
            resources={},
        )
        task.set_completed(result={"output": "value"})
        
        assert task.status == TaskStatus.COMPLETED
        assert task.result == {"output": "value"}

    def test_set_failed(self):
        task = CodeTaskRuntime(
            workflow_id="wf-1",
            task_id="task-1",
            resources={},
        )
        task.set_failed(error="Something went wrong")
        
        assert task.status == TaskStatus.FAILED
        assert task.error == "Something went wrong"

    def test_to_dict(self):
        task = CodeTaskRuntime(
            workflow_id="wf-1",
            task_id="task-1",
            resources={"cpu": 1},
            task_input={"input_params": {}},
            task_output={"output_params": {}},
            code_str="def foo(): pass",
            serialized_code="abc123",
        )
        result = task.to_dict()
        
        assert result["task_type"] == "code"
        assert result["workflow_id"] == "wf-1"
        assert result["task_id"] == "task-1"
        assert result["code_str"] == "def foo(): pass"
        assert result["serialized_code"] == "abc123"

    def test_from_dict(self):
        data = {
            "workflow_id": "wf-1",
            "task_id": "task-1",
            "resources": {"cpu": 2},
            "task_input": {},
            "task_output": {},
            "code_str": "def bar(): pass",
            "serialized_code": "xyz789",
        }
        task = CodeTaskRuntime.from_dict(data)

        assert task.workflow_id == "wf-1"
        assert task.task_id == "task-1"
        assert task.resources == {"cpu": 2}

    def test_from_dict_legacy_code_ser(self):
        """Test backward compatibility with legacy code_ser field."""
        data = {
            "workflow_id": "wf-1",
            "task_id": "task-1",
            "resources": {"cpu": 2},
            "task_input": {},
            "task_output": {},
            "code_str": "def bar(): pass",
            "code_ser": "xyz789",
        }
        task = CodeTaskRuntime.from_dict(data)

        assert task.serialized_code == "xyz789"


class TestLangGraphTaskRuntime:
    def test_creation(self):
        task = LangGraphTaskRuntime(
            workflow_id="wf-1",
            task_id="task-1",
            resources={"cpu": 1},
            serialized_code="abc123",
            serialized_args="args",
            serialized_kwargs="kwargs",
        )
        assert task.task_type == TaskType.LANGGRAPH
        assert task.serialized_code == "abc123"

    def test_to_dict(self):
        task = LangGraphTaskRuntime(
            workflow_id="wf-1",
            task_id="task-1",
            resources={"cpu": 1},
            serialized_code="abc123",
            serialized_args="args",
            serialized_kwargs="kwargs",
        )
        result = task.to_dict()

        assert result["task_type"] == "langgraph"
        assert result["serialized_code"] == "abc123"
        assert result["args"] == "args"
        assert result["kwargs"] == "kwargs"

    def test_from_dict_legacy_code_ser(self):
        """Test backward compatibility with legacy code_ser field."""
        data = {
            "workflow_id": "wf-1",
            "task_id": "task-1",
            "resources": {"cpu": 1},
            "code_ser": "abc123",
            "args": "args",
            "kwargs": "kwargs",
        }
        task = LangGraphTaskRuntime.from_dict(data)

        assert task.serialized_code == "abc123"


class TestCreateTaskRuntime:
    def test_create_code_task(self):
        data = {
            "task_type": "code",
            "workflow_id": "wf-1",
            "task_id": "task-1",
            "resources": {},
        }
        task = create_task_runtime(data)
        assert isinstance(task, CodeTaskRuntime)

    def test_create_langgraph_task(self):
        data = {
            "task_type": "langgraph",
            "workflow_id": "wf-1",
            "task_id": "task-1",
            "resources": {},
        }
        task = create_task_runtime(data)
        assert isinstance(task, LangGraphTaskRuntime)

    def test_unknown_type_raises(self):
        data = {
            "task_type": "unknown",
            "workflow_id": "wf-1",
            "task_id": "task-1",
            "resources": {},
        }
        with pytest.raises(ValueError, match="Unknown task type"):
            create_task_runtime(data)


class TestWorkflowRuntime:
    def test_add_task(self):
        wf = WorkflowRuntime(workflow_id="wf-1")
        task = CodeTaskRuntime(workflow_id="wf-1", task_id="task-1", resources={})
        wf.add_task(task)
        
        assert wf.task_count == 1
        assert wf.get_task("task-1") == task

    def test_get_running_task_refs(self):
        wf = WorkflowRuntime(workflow_id="wf-1")
        task = CodeTaskRuntime(workflow_id="wf-1", task_id="task-1", resources={})
        wf.add_task(task)
        
        assert wf.get_running_task_refs() == []
        
        node = SelectedNode(node_id="node-1", node_ip="192.168.1.1")
        wf.set_task_running("task-1", "ref-123", node)
        
        refs = wf.get_running_task_refs()
        assert len(refs) == 1
        assert refs[0] == "ref-123"


class TestWorkflowRuntimeManager:
    def test_add_task_creates_workflow(self):
        manager = WorkflowRuntimeManager()
        task = CodeTaskRuntime(workflow_id="wf-1", task_id="task-1", resources={})
        manager.add_task(task)
        
        assert manager.workflow_count == 1
        wf = manager.get_workflow("wf-1")
        assert wf is not None
        assert wf.task_count == 1

    def test_clear_workflow(self):
        manager = WorkflowRuntimeManager()
        task = CodeTaskRuntime(workflow_id="wf-1", task_id="task-1", resources={})
        manager.add_task(task)
        
        manager.clear_workflow("wf-1")
        
        assert manager.workflow_count == 0
        assert manager.get_workflow("wf-1") is None


class TestTaskRuntimeRegistry:
    def test_register_and_get(self):
        @dataclass
        class CustomTaskRuntime(BaseTaskRuntime):
            custom_field: str = ""

            @property
            def task_type(self) -> TaskType:
                return TaskType.CODE

            def to_dict(self) -> Dict[str, Any]:
                return {"task_type": "custom", "workflow_id": self.workflow_id, "task_id": self.task_id}

            @classmethod
            def from_dict(cls, data: Dict[str, Any]) -> "CustomTaskRuntime":
                return cls(
                    workflow_id=data["workflow_id"],
                    task_id=data["task_id"],
                    resources=data.get("resources", {}),
                    custom_field=data.get("custom_field", ""),
                )

        TaskRuntimeRegistry.register("custom", CustomTaskRuntime)
        
        assert TaskRuntimeRegistry.get("custom") == CustomTaskRuntime

    def test_get_nonexistent(self):
        result = TaskRuntimeRegistry.get("nonexistent_type")
        assert result is None

    def test_create_with_registry(self):
        data = {
            "task_type": "code",
            "workflow_id": "wf-1",
            "task_id": "task-1",
            "resources": {},
        }
        task = TaskRuntimeRegistry.create(data)
        assert isinstance(task, CodeTaskRuntime)

    def test_create_unknown_type_raises(self):
        data = {
            "task_type": "completely_unknown",
            "workflow_id": "wf-1",
            "task_id": "task-1",
            "resources": {},
        }
        with pytest.raises(ValueError, match="Unknown task type"):
            TaskRuntimeRegistry.create(data)
