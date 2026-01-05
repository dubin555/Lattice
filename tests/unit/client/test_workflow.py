"""
Unit tests for client workflow module.
"""
import pytest
from unittest.mock import MagicMock, patch
from lattice.client.core.workflow import LatticeWorkflow
from lattice.client.core.models import TaskOutput, LatticeTask
from lattice.client.core.decorator import task


class TestLatticeWorkflow:
    def test_creation(self):
        wf = LatticeWorkflow(workflow_id="wf-1", server_url="http://localhost:8000")
        assert wf.workflow_id == "wf-1"
        assert wf.server_url == "http://localhost:8000"
        assert len(wf._tasks) == 0

    def test_server_url_trailing_slash_stripped(self):
        wf = LatticeWorkflow(workflow_id="wf-1", server_url="http://localhost:8000/")
        assert wf.server_url == "http://localhost:8000"

    def test_repr(self):
        wf = LatticeWorkflow(workflow_id="12345678-abcd-efgh", server_url="http://localhost:8000")
        repr_str = repr(wf)
        assert "LatticeWorkflow" in repr_str
        assert "12345678" in repr_str


class TestBuildTaskInput:
    def test_from_user_input(self):
        wf = LatticeWorkflow(workflow_id="wf-1", server_url="http://localhost:8000")
        
        metadata = MagicMock()
        metadata.inputs = ["x", "y"]
        metadata.data_types = {"x": "str", "y": "int"}
        
        inputs = {"x": "hello", "y": 42}
        result = wf._build_task_input(inputs, metadata)
        
        assert "input_params" in result
        params = result["input_params"]
        assert params["1"]["key"] == "x"
        assert params["1"]["input_schema"] == "from_user"
        assert params["1"]["value"] == "hello"
        assert params["2"]["key"] == "y"
        assert params["2"]["value"] == 42

    def test_from_task_input(self):
        wf = LatticeWorkflow(workflow_id="wf-1", server_url="http://localhost:8000")
        
        metadata = MagicMock()
        metadata.inputs = ["data"]
        metadata.data_types = {"data": "str"}
        
        task_output = TaskOutput(task_id="prev-task", output_key="result")
        inputs = {"data": task_output}
        result = wf._build_task_input(inputs, metadata)
        
        params = result["input_params"]
        assert params["1"]["input_schema"] == "from_task"
        assert params["1"]["value"] == "prev-task.output.result"

    def test_missing_input_uses_empty_string(self):
        wf = LatticeWorkflow(workflow_id="wf-1", server_url="http://localhost:8000")
        
        metadata = MagicMock()
        metadata.inputs = ["missing"]
        metadata.data_types = {"missing": "str"}
        
        result = wf._build_task_input({}, metadata)
        
        params = result["input_params"]
        assert params["1"]["value"] == ""


class TestBuildTaskOutput:
    def test_basic_output(self):
        wf = LatticeWorkflow(workflow_id="wf-1", server_url="http://localhost:8000")
        
        metadata = MagicMock()
        metadata.outputs = ["result", "status"]
        metadata.data_types = {"result": "str", "status": "bool"}
        
        result = wf._build_task_output(metadata)
        
        assert "output_params" in result
        params = result["output_params"]
        assert params["1"]["key"] == "result"
        assert params["1"]["data_type"] == "str"
        assert params["2"]["key"] == "status"
        assert params["2"]["data_type"] == "bool"


class TestAddTaskWithMock:
    @patch("lattice.client.core.workflow.requests")
    def test_add_task_makes_requests(self, mock_requests):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success", "task_id": "task-123"}
        mock_requests.post.return_value = mock_response
        
        wf = LatticeWorkflow(workflow_id="wf-1", server_url="http://localhost:8000")
        
        @task(inputs=["x"], outputs=["y"])
        def sample_task(params):
            return {"y": params["x"]}
        
        result = wf.add_task(task_func=sample_task, inputs={"x": "test"})
        
        assert isinstance(result, LatticeTask)
        assert result.task_id == "task-123"
        assert mock_requests.post.call_count == 2

    @patch("lattice.client.core.workflow.requests")
    def test_add_task_no_func_raises(self, mock_requests):
        wf = LatticeWorkflow(workflow_id="wf-1", server_url="http://localhost:8000")
        
        with pytest.raises(ValueError, match="task_func is required"):
            wf.add_task(task_func=None)

    @patch("lattice.client.core.workflow.requests")
    def test_add_task_failed_response_raises(self, mock_requests):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_requests.post.return_value = mock_response
        
        wf = LatticeWorkflow(workflow_id="wf-1", server_url="http://localhost:8000")
        
        @task(inputs=["x"], outputs=["y"])
        def failing_task(params):
            return {"y": params["x"]}
        
        with pytest.raises(Exception, match="Failed to add task"):
            wf.add_task(task_func=failing_task)


class TestRunWorkflow:
    @patch("lattice.client.core.workflow.requests")
    def test_run_returns_run_id(self, mock_requests):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success", "run_id": "run-456"}
        mock_requests.post.return_value = mock_response
        
        wf = LatticeWorkflow(workflow_id="wf-1", server_url="http://localhost:8000")
        run_id = wf.run()
        
        assert run_id == "run-456"

    @patch("lattice.client.core.workflow.requests")
    def test_run_failed_raises(self, mock_requests):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Error"
        mock_requests.post.return_value = mock_response
        
        wf = LatticeWorkflow(workflow_id="wf-1", server_url="http://localhost:8000")
        
        with pytest.raises(Exception, match="Failed to run workflow"):
            wf.run()


class TestAddEdge:
    @patch("lattice.client.core.workflow.requests")
    def test_add_edge_makes_request(self, mock_requests):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success"}
        mock_requests.post.return_value = mock_response
        
        wf = LatticeWorkflow(workflow_id="wf-1", server_url="http://localhost:8000")
        source = LatticeTask(
            task_id="task-1",
            workflow_id="wf-1",
            server_url="http://localhost:8000",
            task_name="Source",
        )
        target = LatticeTask(
            task_id="task-2",
            workflow_id="wf-1",
            server_url="http://localhost:8000",
            task_name="Target",
        )
        
        wf.add_edge(source, target)
        
        mock_requests.post.assert_called_once()
        call_args = mock_requests.post.call_args
        assert "add_edge" in call_args[0][0]


class TestResultsCache:
    def test_cached_results_returned(self):
        wf = LatticeWorkflow(workflow_id="wf-1", server_url="http://localhost:8000")
        cached_data = [{"type": "finish_task", "data": {"result": "cached"}}]
        wf._results_cache["run-123"] = cached_data
        
        result = wf.get_results("run-123", verbose=False)
        
        assert result == cached_data
