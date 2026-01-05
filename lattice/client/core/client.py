"""
Lattice client for connecting to Lattice server.
"""
import requests

from lattice.client.core.workflow import LatticeWorkflow


class LatticeClient:
    def __init__(self, server_url: str = "http://localhost:8000"):
        self.server_url = server_url.rstrip("/")

    def create_workflow(self) -> LatticeWorkflow:
        url = f"{self.server_url}/create_workflow"
        response = requests.post(url)
        
        if response.status_code != 200:
            raise Exception(f"Failed to create workflow: {response.text}")
        
        data = response.json()
        if data.get("status") != "success":
            raise Exception(f"Failed to create workflow: {data}")
        
        workflow_id = data["workflow_id"]
        return LatticeWorkflow(workflow_id, self.server_url)

    def get_workflow(self, workflow_id: str) -> LatticeWorkflow:
        return LatticeWorkflow(workflow_id, self.server_url)

    def get_ray_head_port(self) -> int:
        url = f"{self.server_url}/get_head_ray_port"
        response = requests.post(url)
        
        if response.status_code != 200:
            raise Exception(f"Failed to get Ray port: {response.text}")
        
        data = response.json()
        return data.get("port")
