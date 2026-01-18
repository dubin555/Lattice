"""
Unit tests for client/langgraph module.
"""
import pytest
from unittest.mock import MagicMock, patch


class TestLangGraphClient:
    @patch("lattice.client.base.requests")
    def test_creation(self, mock_requests):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "workflow_id": "wf-123",
        }
        mock_requests.post.return_value = mock_response

        from lattice.client.langgraph.client import LangGraphClient

        client = LangGraphClient(server_url="http://localhost:8000")

        assert client.server_url == "http://localhost:8000"
        assert client.workflow_id == "wf-123"

    @patch("lattice.client.base.requests")
    def test_server_url_trailing_slash_stripped(self, mock_requests):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"workflow_id": "wf-1"}
        mock_requests.post.return_value = mock_response

        from lattice.client.langgraph.client import LangGraphClient

        client = LangGraphClient(server_url="http://localhost:8000/")

        assert client.server_url == "http://localhost:8000"

    @patch("lattice.client.base.requests")
    def test_creation_failed_raises(self, mock_requests):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_requests.post.return_value = mock_response

        from lattice.client.langgraph.client import LangGraphClient

        with pytest.raises(Exception, match="Request.*failed"):
            LangGraphClient(server_url="http://localhost:8000")


class TestTaskDecorator:
    @patch("lattice.client.base.requests")
    def test_task_decorator_basic(self, mock_requests):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = [
            {"workflow_id": "wf-1"},
            {"status": "success", "task_id": "task-123"},
        ]
        mock_requests.post.return_value = mock_response

        from lattice.client.langgraph.client import LangGraphClient

        client = LangGraphClient(server_url="http://localhost:8000")

        @client.task
        def my_func(x):
            return x * 2

        assert hasattr(my_func, "_task_id")
        assert my_func._task_id == "task-123"
        assert hasattr(my_func, "_is_lattice_task")
        assert my_func._is_lattice_task is True

    @patch("lattice.client.base.requests")
    def test_task_decorator_with_resources(self, mock_requests):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = [
            {"workflow_id": "wf-1"},
            {"status": "success", "task_id": "task-456"},
        ]
        mock_requests.post.return_value = mock_response

        from lattice.client.langgraph.client import LangGraphClient

        client = LangGraphClient(server_url="http://localhost:8000")

        @client.task(resources={"cpu": 4, "gpu": 1})
        def gpu_func(x):
            return x

        assert gpu_func._task_id == "task-456"

    @patch("lattice.client.base.requests")
    def test_task_decorator_invalid_resource_raises(self, mock_requests):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"workflow_id": "wf-1"}
        mock_requests.post.return_value = mock_response

        from lattice.client.langgraph.client import LangGraphClient

        client = LangGraphClient(server_url="http://localhost:8000")

        with pytest.raises(ValueError, match="Invalid resource key"):
            @client.task(resources={"invalid_key": 1})
            def bad_func(x):
                return x


class TestTaskExecution:
    @patch("lattice.client.base.requests")
    def test_task_execution(self, mock_requests):
        mock_responses = [
            MagicMock(status_code=200, json=MagicMock(return_value={"workflow_id": "wf-1"})),
            MagicMock(status_code=200, json=MagicMock(return_value={"task_id": "task-1"})),
            MagicMock(status_code=200, json=MagicMock(return_value={"result": 42})),
        ]
        mock_requests.post.side_effect = mock_responses

        from lattice.client.langgraph.client import LangGraphClient

        client = LangGraphClient(server_url="http://localhost:8000")

        @client.task
        def compute(x):
            return x * 2

        result = compute(21)

        assert result == 42

    @patch("lattice.client.base.requests")
    def test_task_execution_failed_raises(self, mock_requests):
        mock_responses = [
            MagicMock(status_code=200, json=MagicMock(return_value={"workflow_id": "wf-1"})),
            MagicMock(status_code=200, json=MagicMock(return_value={"task_id": "task-1"})),
            MagicMock(status_code=500, text="Task failed"),
        ]
        mock_requests.post.side_effect = mock_responses

        from lattice.client.langgraph.client import LangGraphClient

        client = LangGraphClient(server_url="http://localhost:8000")

        @client.task
        def failing_task(x):
            return x

        with pytest.raises(RuntimeError, match="Failed to execute task"):
            failing_task(1)
