"""
Unit tests for LatticeClient.
"""
import pytest
from unittest.mock import MagicMock, patch
from lattice.client.core.client import LatticeClient
from lattice.client.core.workflow import LatticeWorkflow


class TestLatticeClient:
    def test_creation(self):
        client = LatticeClient(server_url="http://localhost:8000")
        assert client.server_url == "http://localhost:8000"

    def test_server_url_trailing_slash_stripped(self):
        client = LatticeClient(server_url="http://localhost:8000/")
        assert client.server_url == "http://localhost:8000"

    def test_default_server_url(self):
        client = LatticeClient()
        assert client.server_url == "http://localhost:8000"


class TestCreateWorkflow:
    @patch("lattice.client.core.client.requests")
    def test_create_workflow_success(self, mock_requests):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "workflow_id": "wf-123",
        }
        mock_requests.post.return_value = mock_response
        
        client = LatticeClient(server_url="http://localhost:8000")
        workflow = client.create_workflow()
        
        assert isinstance(workflow, LatticeWorkflow)
        assert workflow.workflow_id == "wf-123"

    @patch("lattice.client.core.client.requests")
    def test_create_workflow_failed_status(self, mock_requests):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "error", "message": "Failed"}
        mock_requests.post.return_value = mock_response
        
        client = LatticeClient(server_url="http://localhost:8000")
        
        with pytest.raises(Exception, match="Failed to create workflow"):
            client.create_workflow()

    @patch("lattice.client.core.client.requests")
    def test_create_workflow_http_error(self, mock_requests):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_requests.post.return_value = mock_response
        
        client = LatticeClient(server_url="http://localhost:8000")
        
        with pytest.raises(Exception, match="Failed to create workflow"):
            client.create_workflow()


class TestGetWorkflow:
    def test_get_workflow_returns_lattice_workflow(self):
        client = LatticeClient(server_url="http://localhost:8000")
        workflow = client.get_workflow("existing-wf-id")
        
        assert isinstance(workflow, LatticeWorkflow)
        assert workflow.workflow_id == "existing-wf-id"


class TestGetRayHeadPort:
    @patch("lattice.client.core.client.requests")
    def test_get_ray_head_port_success(self, mock_requests):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"port": 6379}
        mock_requests.post.return_value = mock_response
        
        client = LatticeClient(server_url="http://localhost:8000")
        port = client.get_ray_head_port()
        
        assert port == 6379

    @patch("lattice.client.core.client.requests")
    def test_get_ray_head_port_failed(self, mock_requests):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Error"
        mock_requests.post.return_value = mock_response
        
        client = LatticeClient(server_url="http://localhost:8000")
        
        with pytest.raises(Exception, match="Failed to get Ray port"):
            client.get_ray_head_port()
