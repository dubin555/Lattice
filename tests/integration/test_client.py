"""
Integration tests for LatticeClient.

These tests require a running Lattice server.
"""
import pytest
import requests

from lattice.client.core.client import LatticeClient
from lattice.client.core.decorator import task


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


@pytest.fixture
def client(check_server):
    return LatticeClient(server_url=SERVER_URL)


@pytest.mark.integration
class TestLatticeClientIntegration:
    def test_create_workflow(self, client):
        workflow = client.create_workflow()
        assert workflow is not None
        assert workflow.workflow_id is not None

    def test_get_ray_head_port(self, client):
        port = client.get_ray_head_port()
        assert isinstance(port, int)
        assert port > 0


@pytest.mark.integration
class TestLatticeWorkflowIntegration:
    def test_add_single_task(self, client):
        @task(inputs=["x"], outputs=["y"])
        def simple_task(params):
            return {"y": params["x"] + " processed"}
        
        workflow = client.create_workflow()
        task_obj = workflow.add_task(
            task_func=simple_task,
            inputs={"x": "hello"},
        )
        
        assert task_obj is not None
        assert task_obj.task_id is not None

    def test_add_multiple_tasks(self, client):
        @task(inputs=["a"], outputs=["b"])
        def task1(params):
            return {"b": params["a"] * 2}
        
        @task(inputs=["b"], outputs=["c"])
        def task2(params):
            return {"c": params["b"] + 10}
        
        workflow = client.create_workflow()
        
        t1 = workflow.add_task(task_func=task1, inputs={"a": 5})
        t2 = workflow.add_task(
            task_func=task2,
            inputs={"b": t1.outputs["b"]},
        )
        
        assert t1.task_id is not None
        assert t2.task_id is not None
        assert t1.task_id != t2.task_id

    def test_task_outputs_accessible(self, client):
        @task(inputs=["input"], outputs=["output1", "output2"])
        def multi_output(params):
            return {
                "output1": params["input"],
                "output2": params["input"] + "_extra",
            }
        
        workflow = client.create_workflow()
        t = workflow.add_task(task_func=multi_output, inputs={"input": "test"})
        
        assert "output1" in t.outputs
        assert "output2" in t.outputs

    def test_workflow_repr(self, client):
        workflow = client.create_workflow()
        repr_str = repr(workflow)
        assert "LatticeWorkflow" in repr_str
