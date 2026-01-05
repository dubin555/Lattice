"""
Unit tests for core/workflow module.
"""
import pytest
from lattice.core.workflow.base import (
    TaskType,
    CodeTask,
    LangGraphTask,
    Workflow,
    LangGraphWorkflow,
)


class TestCodeTask:
    def test_creation(self):
        task = CodeTask(
            workflow_id="wf-1",
            task_id="task-1",
            task_name="Test Task",
        )
        assert task.workflow_id == "wf-1"
        assert task.task_id == "task-1"
        assert task.task_name == "Test Task"
        assert task.task_type == TaskType.CODE
        assert task.completed is False

    def test_save(self):
        task = CodeTask(
            workflow_id="wf-1",
            task_id="task-1",
            task_name="Test Task",
        )
        task.save(
            task_input={"input_params": {}},
            task_output={"output_params": {}},
            code_str="def foo(): pass",
            serialized_code="abc123",
            resources={"cpu": 2},
        )
        
        assert task.task_input == {"input_params": {}}
        assert task.code_str == "def foo(): pass"
        assert task.serialized_code == "abc123"
        assert task.resources == {"cpu": 2}

    def test_to_dict(self):
        task = CodeTask(
            workflow_id="wf-1",
            task_id="task-1",
            task_name="Test Task",
        )
        task.save(
            task_input={"input_params": {}},
            task_output={"output_params": {}},
            code_str="def foo(): pass",
            resources={"cpu": 1},
        )
        
        result = task.to_dict()
        assert result["task_type"] == "code"
        assert result["workflow_id"] == "wf-1"
        assert result["task_id"] == "task-1"
        assert result["task_name"] == "Test Task"


class TestLangGraphTask:
    def test_creation(self):
        task = LangGraphTask(
            workflow_id="wf-1",
            task_id="task-1",
            task_name="LG Task",
            serialized_code="abc123",
        )
        assert task.task_type == TaskType.LANGGRAPH
        assert task.serialized_code == "abc123"

    def test_set_args_kwargs(self):
        task = LangGraphTask(
            workflow_id="wf-1",
            task_id="task-1",
            task_name="LG Task",
            serialized_code="abc123",
        )
        task.set_args("args_data")
        task.set_kwargs("kwargs_data")
        
        assert task.serialized_args == "args_data"
        assert task.serialized_kwargs == "kwargs_data"


class TestWorkflow:
    def test_creation(self):
        wf = Workflow(workflow_id="wf-1")
        assert wf.workflow_id == "wf-1"
        assert wf.task_count == 0

    def test_add_task(self):
        wf = Workflow(workflow_id="wf-1")
        task = CodeTask(workflow_id="wf-1", task_id="task-1", task_name="Task 1")
        wf.add_task("task-1", task)
        
        assert wf.task_count == 1
        assert wf.get_task("task-1") == task

    def test_add_task_id_mismatch_raises(self):
        wf = Workflow(workflow_id="wf-1")
        task = CodeTask(workflow_id="wf-1", task_id="task-1", task_name="Task 1")
        
        with pytest.raises(ValueError, match="task_id must match"):
            wf.add_task("task-2", task)

    def test_remove_task(self):
        wf = Workflow(workflow_id="wf-1")
        task = CodeTask(workflow_id="wf-1", task_id="task-1", task_name="Task 1")
        wf.add_task("task-1", task)
        wf.remove_task("task-1")
        
        assert wf.task_count == 0
        assert wf.get_task("task-1") is None

    def test_add_edge(self):
        wf = Workflow(workflow_id="wf-1")
        task1 = CodeTask(workflow_id="wf-1", task_id="task-1", task_name="Task 1")
        task2 = CodeTask(workflow_id="wf-1", task_id="task-2", task_name="Task 2")
        wf.add_task("task-1", task1)
        wf.add_task("task-2", task2)
        
        wf.add_edge("task-1", "task-2")
        
        edges = wf.get_graph_edges()
        assert ("task-1", "task-2") in edges

    def test_add_edge_nonexistent_task_raises(self):
        wf = Workflow(workflow_id="wf-1")
        task1 = CodeTask(workflow_id="wf-1", task_id="task-1", task_name="Task 1")
        wf.add_task("task-1", task1)
        
        with pytest.raises(ValueError, match="Both tasks must exist"):
            wf.add_edge("task-1", "task-999")

    def test_add_edge_creates_cycle_raises(self):
        wf = Workflow(workflow_id="wf-1")
        task1 = CodeTask(workflow_id="wf-1", task_id="task-1", task_name="Task 1")
        task2 = CodeTask(workflow_id="wf-1", task_id="task-2", task_name="Task 2")
        wf.add_task("task-1", task1)
        wf.add_task("task-2", task2)
        
        wf.add_edge("task-1", "task-2")
        
        with pytest.raises(ValueError, match="cycle"):
            wf.add_edge("task-2", "task-1")

    def test_get_start_tasks(self):
        wf = Workflow(workflow_id="wf-1")
        task1 = CodeTask(workflow_id="wf-1", task_id="task-1", task_name="Task 1")
        task2 = CodeTask(workflow_id="wf-1", task_id="task-2", task_name="Task 2")
        task3 = CodeTask(workflow_id="wf-1", task_id="task-3", task_name="Task 3")
        
        wf.add_task("task-1", task1)
        wf.add_task("task-2", task2)
        wf.add_task("task-3", task3)
        
        wf.add_edge("task-1", "task-2")
        wf.add_edge("task-2", "task-3")
        
        start_tasks = wf.get_start_tasks()
        assert len(start_tasks) == 1
        assert start_tasks[0].task_id == "task-1"

    def test_get_ready_tasks_after_completion(self):
        wf = Workflow(workflow_id="wf-1")
        task1 = CodeTask(workflow_id="wf-1", task_id="task-1", task_name="Task 1")
        task2 = CodeTask(workflow_id="wf-1", task_id="task-2", task_name="Task 2")
        
        wf.add_task("task-1", task1)
        wf.add_task("task-2", task2)
        wf.add_edge("task-1", "task-2")
        
        ready_tasks = wf.get_ready_tasks_after_completion("task-1")
        
        assert len(ready_tasks) == 1
        assert ready_tasks[0].task_id == "task-2"
        assert task1.completed is True

    def test_get_task_info_list(self):
        wf = Workflow(workflow_id="wf-1")
        task1 = CodeTask(workflow_id="wf-1", task_id="task-1", task_name="Task 1")
        wf.add_task("task-1", task1)
        
        info = wf.get_task_info_list()
        assert len(info) == 1
        assert info[0]["id"] == "task-1"
        assert info[0]["name"] == "Task 1"


class TestLangGraphWorkflow:
    def test_creation(self):
        wf = LangGraphWorkflow(workflow_id="wf-1")
        assert wf.workflow_id == "wf-1"

    def test_add_task(self):
        wf = LangGraphWorkflow(workflow_id="wf-1")
        task = LangGraphTask(
            workflow_id="wf-1",
            task_id="task-1",
            task_name="LG Task",
            serialized_code="abc123",
        )
        wf.add_task("task-1", task)
        
        assert wf.get_task("task-1") == task
