"""
Unit tests for API schemas.
"""
import pytest
from pydantic import ValidationError

from lattice.api.models.schemas import (
    CreateWorkflowResponse,
    AddTaskRequest,
    AddTaskResponse,
    SaveTaskRequest,
    SaveTaskResponse,
    AddEdgeRequest,
    AddEdgeResponse,
    RunWorkflowRequest,
    RunWorkflowResponse,
    GetTasksResponse,
    AddLangGraphTaskRequest,
    RunLangGraphTaskRequest,
    RunLangGraphTaskResponse,
    StartWorkerRequest,
    StartWorkerResponse,
    GetRayPortResponse,
    StartLLMInstanceRequest,
    StartLLMInstanceResponse,
    StopLLMInstanceRequest,
    StopLLMInstanceResponse,
    ErrorResponse,
)


class TestCreateWorkflowResponse:
    def test_valid(self):
        resp = CreateWorkflowResponse(status="success", workflow_id="wf-123")
        assert resp.status == "success"
        assert resp.workflow_id == "wf-123"

    def test_missing_field_raises(self):
        with pytest.raises(ValidationError):
            CreateWorkflowResponse(status="success")


class TestAddTaskRequest:
    def test_valid(self):
        req = AddTaskRequest(
            workflow_id="wf-1",
            task_type="code",
            task_name="Test Task",
        )
        assert req.workflow_id == "wf-1"
        assert req.task_type == "code"
        assert req.task_name == "Test Task"

    def test_default_task_type(self):
        req = AddTaskRequest(workflow_id="wf-1", task_name="Test")
        assert req.task_type == "code"

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            AddTaskRequest(workflow_id="wf-1")


class TestAddTaskResponse:
    def test_valid(self):
        resp = AddTaskResponse(status="success", task_id="task-123")
        assert resp.status == "success"
        assert resp.task_id == "task-123"


class TestSaveTaskRequest:
    def test_valid_with_code_str(self):
        req = SaveTaskRequest(
            workflow_id="wf-1",
            task_id="task-1",
            task_input={"input_params": {}},
            task_output={"output_params": {}},
            resources={"cpu": 1},
            code_str="def foo(): pass",
        )
        assert req.code_str == "def foo(): pass"
        assert req.code_ser is None

    def test_valid_with_code_ser(self):
        req = SaveTaskRequest(
            workflow_id="wf-1",
            task_id="task-1",
            task_input={},
            task_output={},
            resources={},
            code_ser="abc123",
        )
        assert req.code_ser == "abc123"


class TestSaveTaskResponse:
    def test_valid(self):
        resp = SaveTaskResponse(status="success")
        assert resp.status == "success"


class TestAddEdgeRequest:
    def test_valid(self):
        req = AddEdgeRequest(
            workflow_id="wf-1",
            source_task_id="task-1",
            target_task_id="task-2",
        )
        assert req.workflow_id == "wf-1"
        assert req.source_task_id == "task-1"
        assert req.target_task_id == "task-2"


class TestAddEdgeResponse:
    def test_valid(self):
        resp = AddEdgeResponse(status="success")
        assert resp.status == "success"


class TestRunWorkflowRequest:
    def test_valid(self):
        req = RunWorkflowRequest(workflow_id="wf-1")
        assert req.workflow_id == "wf-1"


class TestRunWorkflowResponse:
    def test_valid(self):
        resp = RunWorkflowResponse(status="success", run_id="run-123")
        assert resp.status == "success"
        assert resp.run_id == "run-123"


class TestGetTasksResponse:
    def test_valid(self):
        resp = GetTasksResponse(
            status="success",
            tasks=[{"id": "task-1", "name": "Task 1"}],
        )
        assert resp.status == "success"
        assert len(resp.tasks) == 1

    def test_empty_tasks(self):
        resp = GetTasksResponse(status="success", tasks=[])
        assert resp.tasks == []


class TestAddLangGraphTaskRequest:
    def test_valid(self):
        req = AddLangGraphTaskRequest(
            workflow_id="wf-1",
            task_name="LG Task",
            code_ser="abc123",
            resources={"cpu": 1, "gpu": 0},
        )
        assert req.task_type == "langgraph"
        assert req.code_ser == "abc123"


class TestRunLangGraphTaskRequest:
    def test_valid(self):
        req = RunLangGraphTaskRequest(
            workflow_id="wf-1",
            task_id="task-1",
            args="args_data",
            kwargs="kwargs_data",
        )
        assert req.args == "args_data"
        assert req.kwargs == "kwargs_data"


class TestRunLangGraphTaskResponse:
    def test_valid(self):
        resp = RunLangGraphTaskResponse(status="success", result={"output": "value"})
        assert resp.status == "success"
        assert resp.result == {"output": "value"}


class TestStartWorkerRequest:
    def test_valid(self):
        req = StartWorkerRequest(
            node_ip="192.168.1.1",
            node_id="node-1",
            resources={"cpu": 8, "cpu_mem": 16000},
        )
        assert req.node_ip == "192.168.1.1"
        assert req.node_id == "node-1"


class TestStartWorkerResponse:
    def test_valid(self):
        resp = StartWorkerResponse(status="success")
        assert resp.status == "success"


class TestGetRayPortResponse:
    def test_valid(self):
        resp = GetRayPortResponse(status="success", port=6379)
        assert resp.port == 6379


class TestStartLLMInstanceRequest:
    def test_valid(self):
        req = StartLLMInstanceRequest(model="gpt-4")
        assert req.model == "gpt-4"
        assert req.cpu_nums == 1
        assert req.gpu_nums == 0

    def test_with_resources(self):
        req = StartLLMInstanceRequest(
            model="llama",
            cpu_nums=4,
            gpu_nums=2,
            memory=8000,
            gpu_mem=16000,
        )
        assert req.cpu_nums == 4
        assert req.gpu_nums == 2
        assert req.gpu_mem == 16000


class TestStartLLMInstanceResponse:
    def test_valid(self):
        resp = StartLLMInstanceResponse(
            status="success",
            host="192.168.1.1",
            port=8080,
            instance_id="inst-123",
        )
        assert resp.host == "192.168.1.1"
        assert resp.port == 8080


class TestStopLLMInstanceRequest:
    def test_valid(self):
        req = StopLLMInstanceRequest(instance_id="inst-123")
        assert req.instance_id == "inst-123"


class TestStopLLMInstanceResponse:
    def test_valid(self):
        resp = StopLLMInstanceResponse(status="success")
        assert resp.status == "success"


class TestErrorResponse:
    def test_valid(self):
        resp = ErrorResponse(detail="Something went wrong")
        assert resp.detail == "Something went wrong"
