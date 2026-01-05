"""
Integration tests for workflow API.

These tests require a running Lattice server.
"""
import pytest
import requests
import time


SERVER_URL = "http://localhost:8000"


def server_is_running():
    try:
        response = requests.get(f"{SERVER_URL}/docs", timeout=2)
        return response.status_code == 200
    except requests.RequestException:
        return False


@pytest.fixture(scope="module")
def check_server():
    if not server_is_running():
        pytest.skip("Lattice server not running at localhost:8000")


@pytest.mark.integration
class TestWorkflowIntegration:
    def test_create_workflow(self, check_server):
        response = requests.post(f"{SERVER_URL}/create_workflow")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "workflow_id" in data
        return data["workflow_id"]

    def test_add_task_to_workflow(self, check_server):
        wf_response = requests.post(f"{SERVER_URL}/create_workflow")
        workflow_id = wf_response.json()["workflow_id"]
        
        response = requests.post(f"{SERVER_URL}/add_task", json={
            "workflow_id": workflow_id,
            "task_type": "code",
            "task_name": "Integration Test Task",
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "task_id" in data

    def test_save_task(self, check_server):
        wf_response = requests.post(f"{SERVER_URL}/create_workflow")
        workflow_id = wf_response.json()["workflow_id"]
        
        task_response = requests.post(f"{SERVER_URL}/add_task", json={
            "workflow_id": workflow_id,
            "task_type": "code",
            "task_name": "Test Task",
        })
        task_id = task_response.json()["task_id"]
        
        response = requests.post(f"{SERVER_URL}/save_task", json={
            "workflow_id": workflow_id,
            "task_id": task_id,
            "task_input": {"input_params": {}},
            "task_output": {"output_params": {}},
            "resources": {"cpu": 1, "cpu_mem": 0, "gpu": 0, "gpu_mem": 0},
            "code_str": "def test_task(params): return {'result': 'ok'}",
        })
        
        assert response.status_code == 200
        assert response.json()["status"] == "success"

    def test_get_workflow_tasks(self, check_server):
        wf_response = requests.post(f"{SERVER_URL}/create_workflow")
        workflow_id = wf_response.json()["workflow_id"]
        
        requests.post(f"{SERVER_URL}/add_task", json={
            "workflow_id": workflow_id,
            "task_type": "code",
            "task_name": "Task 1",
        })
        requests.post(f"{SERVER_URL}/add_task", json={
            "workflow_id": workflow_id,
            "task_type": "code",
            "task_name": "Task 2",
        })
        
        response = requests.get(f"{SERVER_URL}/get_workflow_tasks/{workflow_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert len(data["tasks"]) == 2

    def test_add_and_del_edge(self, check_server):
        wf_response = requests.post(f"{SERVER_URL}/create_workflow")
        workflow_id = wf_response.json()["workflow_id"]
        
        task1_response = requests.post(f"{SERVER_URL}/add_task", json={
            "workflow_id": workflow_id,
            "task_type": "code",
            "task_name": "Task 1",
        })
        task1_id = task1_response.json()["task_id"]
        
        task2_response = requests.post(f"{SERVER_URL}/add_task", json={
            "workflow_id": workflow_id,
            "task_type": "code",
            "task_name": "Task 2",
        })
        task2_id = task2_response.json()["task_id"]
        
        add_response = requests.post(f"{SERVER_URL}/add_edge", json={
            "workflow_id": workflow_id,
            "source_task_id": task1_id,
            "target_task_id": task2_id,
        })
        assert add_response.status_code == 200
        
        del_response = requests.post(f"{SERVER_URL}/del_edge", json={
            "workflow_id": workflow_id,
            "source_task_id": task1_id,
            "target_task_id": task2_id,
        })
        assert del_response.status_code == 200

    def test_del_task(self, check_server):
        wf_response = requests.post(f"{SERVER_URL}/create_workflow")
        workflow_id = wf_response.json()["workflow_id"]
        
        task_response = requests.post(f"{SERVER_URL}/add_task", json={
            "workflow_id": workflow_id,
            "task_type": "code",
            "task_name": "To Delete",
        })
        task_id = task_response.json()["task_id"]
        
        response = requests.post(f"{SERVER_URL}/del_task", json={
            "workflow_id": workflow_id,
            "task_id": task_id,
        })
        
        assert response.status_code == 200
        assert response.json()["status"] == "success"


@pytest.mark.integration
class TestWorkerIntegration:
    def test_get_ray_port(self, check_server):
        response = requests.post(f"{SERVER_URL}/get_head_ray_port")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "port" in data
        assert isinstance(data["port"], int)
