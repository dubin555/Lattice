"""
Lattice client for connecting to Lattice server.
"""
from lattice.client.base import BaseClient
from lattice.client.core.workflow import LatticeWorkflow


class LatticeClient(BaseClient):
    """
    Main client for interacting with the Lattice server.

    Inherits from BaseClient to provide common HTTP request functionality.
    """

    def __init__(self, server_url: str = "http://localhost:8000"):
        """
        Initialize the Lattice client.

        Args:
            server_url: The URL of the Lattice server.
        """
        super().__init__(server_url)

    def create_workflow(self) -> LatticeWorkflow:
        """
        Create a new workflow on the server.

        Returns:
            A LatticeWorkflow instance for building and executing the workflow.

        Raises:
            LatticeClientError: If the request fails.
        """
        data = self._post("/create_workflow")

        if data.get("status") != "success":
            from lattice.exceptions import LatticeClientError
            raise LatticeClientError(
                f"Failed to create workflow: {data}",
                details={"response": data}
            )

        workflow_id = data["workflow_id"]
        return LatticeWorkflow(workflow_id, self)

    def get_workflow(self, workflow_id: str) -> LatticeWorkflow:
        """
        Get an existing workflow by ID.

        Args:
            workflow_id: The ID of the workflow.

        Returns:
            A LatticeWorkflow instance.
        """
        return LatticeWorkflow(workflow_id, self)

    def get_ray_head_port(self) -> int:
        """
        Get the Ray head port from the server.

        Returns:
            The Ray head port number.

        Raises:
            LatticeClientError: If the request fails.
        """
        data = self._post("/get_head_ray_port")
        return data.get("port")
