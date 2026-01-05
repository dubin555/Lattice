"""
Shared test fixtures for lattice tests.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock


@pytest.fixture
def mock_orchestrator():
    orchestrator = MagicMock()
    orchestrator.ray_head_port = 6379
    orchestrator.create_workflow = MagicMock(return_value=MagicMock())
    orchestrator.get_workflow = MagicMock(return_value=MagicMock())
    orchestrator.get_workflow_tasks = MagicMock(return_value=[])
    orchestrator.run_workflow = MagicMock(return_value="run-123")
    orchestrator.wait_workflow_complete = AsyncMock(return_value=[])
    orchestrator.stop_workflow = AsyncMock()
    orchestrator.add_worker = MagicMock()
    orchestrator.remove_worker = MagicMock()
    orchestrator.run_langgraph_task = AsyncMock(return_value={"result": "ok"})
    return orchestrator


@pytest.fixture
def sample_workflow_id():
    return "test-workflow-123"


@pytest.fixture
def sample_task_id():
    return "test-task-456"


@pytest.fixture
def sample_resources():
    return {"cpu": 1, "cpu_mem": 0, "gpu": 0, "gpu_mem": 0}


@pytest.fixture
def sample_task_input():
    return {
        "input_params": {
            "1": {
                "key": "input1",
                "input_schema": "from_user",
                "data_type": "str",
                "value": "test_value",
            }
        }
    }


@pytest.fixture
def sample_task_output():
    return {
        "output_params": {
            "1": {
                "key": "output1",
                "data_type": "str",
            }
        }
    }


@pytest.fixture
def sample_code_str():
    return """
def my_task(params):
    return {"output1": params.get("input1", "") + " processed"}
"""
