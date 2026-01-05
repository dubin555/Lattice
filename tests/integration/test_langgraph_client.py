"""
Integration tests for LangGraph client.

These tests require a running Lattice server.
"""
import pytest
import requests
import base64
import cloudpickle

from lattice.client.langgraph.client import LangGraphClient


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
def langgraph_client(check_server):
    return LangGraphClient(server_url=SERVER_URL)


@pytest.mark.integration
class TestLangGraphClientIntegration:
    def test_client_creation(self, langgraph_client):
        assert langgraph_client.workflow_id is not None

    def test_task_decorator(self, langgraph_client):
        @langgraph_client.task
        def simple_func(x):
            return x * 2
        
        assert hasattr(simple_func, "_task_id")
        assert hasattr(simple_func, "_is_lattice_task")
        assert simple_func._is_lattice_task is True

    def test_task_decorator_with_resources(self, langgraph_client):
        @langgraph_client.task(resources={"cpu": 2, "gpu": 1})
        def gpu_func(x):
            return x
        
        assert hasattr(gpu_func, "_task_id")
        assert gpu_func._is_lattice_task is True


@pytest.mark.integration
class TestLangGraphClientUnit:
    def test_default_resources(self, check_server):
        client = LangGraphClient(server_url=SERVER_URL)
        assert client._default_resources == {
            "cpu": 1,
            "gpu": 0,
            "cpu_mem": 0,
            "gpu_mem": 0,
        }

    def test_post_method(self, check_server):
        client = LangGraphClient(server_url=SERVER_URL)
        assert client.workflow_id is not None

    def test_invalid_resource_key_raises(self, check_server):
        client = LangGraphClient(server_url=SERVER_URL)
        
        with pytest.raises(ValueError, match="Invalid resource key"):
            @client.task(resources={"invalid_key": 1})
            def bad_func(x):
                return x
