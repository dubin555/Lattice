"""
Custom exception hierarchy for Lattice.
"""
from typing import Optional, Dict, Any


class LatticeError(Exception):
    """Base exception for all Lattice errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} - Details: {self.details}"
        return self.message


class ClientError(LatticeError):
    """Base exception for client-side errors."""
    pass


class LatticeClientError(ClientError):
    """Exception raised when a client HTTP request fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)
        self.status_code = details.get("status_code") if details else None
        self.response_text = details.get("response_text") if details else None


class ServerError(LatticeError):
    """Base exception for server-side errors."""
    pass


class ExecutorError(LatticeError):
    """Base exception for executor errors."""
    pass


class ValidationError(LatticeError):
    """Base exception for validation errors."""
    pass


class WorkflowNotFoundError(ClientError):
    def __init__(self, workflow_id: str):
        super().__init__(f"Workflow not found: {workflow_id}", {"workflow_id": workflow_id})
        self.workflow_id = workflow_id


class TaskNotFoundError(ClientError):
    def __init__(self, task_id: str, workflow_id: Optional[str] = None):
        details = {"task_id": task_id}
        if workflow_id:
            details["workflow_id"] = workflow_id
        super().__init__(f"Task not found: {task_id}", details)
        self.task_id = task_id
        self.workflow_id = workflow_id


class OrchestratorNotInitializedError(ServerError):
    def __init__(self):
        super().__init__("Orchestrator not initialized. Call initialize() first.")


class TaskExecutionError(ExecutorError):
    def __init__(self, task_id: str, cause: Optional[str] = None):
        message = f"Task execution failed: {task_id}"
        if cause:
            message = f"{message} - {cause}"
        super().__init__(message, {"task_id": task_id, "cause": cause})
        self.task_id = task_id
        self.cause = cause


class TaskCancelledError(ExecutorError):
    def __init__(self, task_id: str):
        super().__init__(f"Task cancelled: {task_id}", {"task_id": task_id})
        self.task_id = task_id


class NodeFailedError(ExecutorError):
    def __init__(self, node_id: str, task_id: Optional[str] = None):
        details = {"node_id": node_id}
        if task_id:
            details["task_id"] = task_id
        super().__init__(f"Node failed: {node_id}", details)
        self.node_id = node_id
        self.task_id = task_id


class CyclicDependencyError(ValidationError):
    def __init__(self, cycle: Optional[list] = None):
        super().__init__(
            "Cyclic dependency detected in workflow",
            {"cycle": cycle} if cycle else {}
        )
        self.cycle = cycle
