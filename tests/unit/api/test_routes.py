"""
Unit tests for API routes.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from lattice.api.routes import workflow, langgraph, worker
from lattice.api.dependencies import set_orchestrator
from lattice.core.workflow.base import Workflow, CodeTask, LangGraphWorkflow, LangGraphTask


@pytest.fixture
def mock_orchestrator():
    orchestrator = MagicMock()
    orchestrator.ray_head_port = 6379
    return orchestrator


@pytest.fixture
def workflow_app(mock_orchestrator):
    app = FastAPI()
    set_orchestrator(mock_orchestrator)
    app.include_router(workflow.router)
    return app


@pytest.fixture
def langgraph_app(mock_orchestrator):
    app = FastAPI()
    set_orchestrator(mock_orchestrator)
    app.include_router(langgraph.router)
    return app


@pytest.fixture
def worker_app(mock_orchestrator):
    app = FastAPI()
    set_orchestrator(mock_orchestrator)
    app.include_router(worker.router)
    return app


class TestWorkflowRoutes:
    def test_create_workflow(self, workflow_app, mock_orchestrator):
        mock_workflow = MagicMock()
        mock_orchestrator.create_workflow.return_value = mock_workflow
        
        client = TestClient(workflow_app)
        response = client.post("/create_workflow")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "workflow_id" in data

    def test_add_task(self, workflow_app, mock_orchestrator):
        mock_workflow = Workflow(workflow_id="wf-1")
        mock_orchestrator.get_workflow.return_value = mock_workflow
        
        client = TestClient(workflow_app)
        response = client.post("/add_task", json={
            "workflow_id": "wf-1",
            "task_type": "code",
            "task_name": "Test Task",
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "task_id" in data

    def test_add_task_workflow_not_found(self, workflow_app, mock_orchestrator):
        mock_orchestrator.get_workflow.return_value = None
        
        client = TestClient(workflow_app)
        response = client.post("/add_task", json={
            "workflow_id": "nonexistent",
            "task_type": "code",
            "task_name": "Test Task",
        })
        
        assert response.status_code == 404

    def test_save_task(self, workflow_app, mock_orchestrator):
        mock_workflow = Workflow(workflow_id="wf-1")
        mock_task = CodeTask(workflow_id="wf-1", task_id="task-1", task_name="Test")
        mock_workflow.add_task("task-1", mock_task)
        mock_orchestrator.get_workflow.return_value = mock_workflow
        
        client = TestClient(workflow_app)
        response = client.post("/save_task", json={
            "workflow_id": "wf-1",
            "task_id": "task-1",
            "task_input": {"input_params": {}},
            "task_output": {"output_params": {}},
            "resources": {"cpu": 1},
            "code_str": "def foo(): pass",
        })
        
        assert response.status_code == 200
        assert response.json()["status"] == "success"

    def test_save_task_no_code_raises(self, workflow_app, mock_orchestrator):
        mock_workflow = Workflow(workflow_id="wf-1")
        mock_task = CodeTask(workflow_id="wf-1", task_id="task-1", task_name="Test")
        mock_workflow.add_task("task-1", mock_task)
        mock_orchestrator.get_workflow.return_value = mock_workflow
        
        client = TestClient(workflow_app)
        response = client.post("/save_task", json={
            "workflow_id": "wf-1",
            "task_id": "task-1",
            "task_input": {},
            "task_output": {},
            "resources": {},
        })
        
        assert response.status_code == 400

    def test_add_edge(self, workflow_app, mock_orchestrator):
        mock_workflow = Workflow(workflow_id="wf-1")
        task1 = CodeTask(workflow_id="wf-1", task_id="task-1", task_name="Task 1")
        task2 = CodeTask(workflow_id="wf-1", task_id="task-2", task_name="Task 2")
        mock_workflow.add_task("task-1", task1)
        mock_workflow.add_task("task-2", task2)
        mock_orchestrator.get_workflow.return_value = mock_workflow
        
        client = TestClient(workflow_app)
        response = client.post("/add_edge", json={
            "workflow_id": "wf-1",
            "source_task_id": "task-1",
            "target_task_id": "task-2",
        })
        
        assert response.status_code == 200
        assert response.json()["status"] == "success"

    def test_del_edge(self, workflow_app, mock_orchestrator):
        mock_workflow = Workflow(workflow_id="wf-1")
        task1 = CodeTask(workflow_id="wf-1", task_id="task-1", task_name="Task 1")
        task2 = CodeTask(workflow_id="wf-1", task_id="task-2", task_name="Task 2")
        mock_workflow.add_task("task-1", task1)
        mock_workflow.add_task("task-2", task2)
        mock_workflow.add_edge("task-1", "task-2")
        mock_orchestrator.get_workflow.return_value = mock_workflow
        
        client = TestClient(workflow_app)
        response = client.post("/del_edge", json={
            "workflow_id": "wf-1",
            "source_task_id": "task-1",
            "target_task_id": "task-2",
        })
        
        assert response.status_code == 200

    def test_del_task(self, workflow_app, mock_orchestrator):
        mock_workflow = Workflow(workflow_id="wf-1")
        mock_task = CodeTask(workflow_id="wf-1", task_id="task-1", task_name="Test")
        mock_workflow.add_task("task-1", mock_task)
        mock_orchestrator.get_workflow.return_value = mock_workflow
        
        client = TestClient(workflow_app)
        response = client.post("/del_task", json={
            "workflow_id": "wf-1",
            "task_id": "task-1",
        })
        
        assert response.status_code == 200
        assert response.json()["status"] == "success"

    def test_get_workflow_tasks(self, workflow_app, mock_orchestrator):
        mock_orchestrator.get_workflow_tasks.return_value = [
            {"id": "task-1", "name": "Task 1"},
            {"id": "task-2", "name": "Task 2"},
        ]
        
        client = TestClient(workflow_app)
        response = client.get("/get_workflow_tasks/wf-1")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert len(data["tasks"]) == 2

    def test_run_workflow(self, workflow_app, mock_orchestrator):
        mock_orchestrator.run_workflow.return_value = "run-123"
        
        client = TestClient(workflow_app)
        response = client.post("/run_workflow", json={
            "workflow_id": "wf-1",
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["run_id"] == "run-123"


class TestLangGraphRoutes:
    def test_add_langgraph_task_new_workflow(self, langgraph_app, mock_orchestrator):
        mock_orchestrator.get_workflow.return_value = None
        mock_orchestrator._workflows = {}
        
        client = TestClient(langgraph_app)
        response = client.post("/add_langgraph_task", json={
            "workflow_id": "wf-1",
            "task_type": "langgraph",
            "task_name": "LG Task",
            "code_ser": "abc123",
            "resources": {"cpu": 1},
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "task_id" in data

    def test_add_langgraph_task_existing_workflow(self, langgraph_app, mock_orchestrator):
        existing_workflow = LangGraphWorkflow(workflow_id="wf-1")
        mock_orchestrator.get_workflow.return_value = existing_workflow
        
        client = TestClient(langgraph_app)
        response = client.post("/add_langgraph_task", json={
            "workflow_id": "wf-1",
            "task_type": "langgraph",
            "task_name": "Another LG Task",
            "code_ser": "xyz789",
            "resources": {"cpu": 2},
        })
        
        assert response.status_code == 200


class TestWorkerRoutes:
    def test_start_worker(self, worker_app, mock_orchestrator):
        client = TestClient(worker_app)
        response = client.post("/start_worker", json={
            "node_ip": "192.168.1.1",
            "node_id": "node-1",
            "resources": {"cpu": 8, "cpu_mem": 16000},
        })
        
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        mock_orchestrator.add_worker.assert_called_once()

    def test_get_head_ray_port(self, worker_app, mock_orchestrator):
        mock_orchestrator.ray_head_port = 6379
        
        client = TestClient(worker_app)
        response = client.post("/get_head_ray_port")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["port"] == 6379
