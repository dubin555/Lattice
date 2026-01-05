"""
Custom exception hierarchy for Lattice.

This module defines a structured exception hierarchy for better error handling
and debugging across the Lattice framework.
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


# =============================================================================
# Client Errors
# =============================================================================

class ClientError(LatticeError):
    """Base exception for client-side errors."""
    pass


class ConnectionError(ClientError):
    """Failed to connect to Lattice server."""
    pass


class WorkflowError(ClientError):
    """Error related to workflow operations."""
    pass


class WorkflowNotFoundError(WorkflowError):
    """Workflow not found."""
    
    def __init__(self, workflow_id: str):
        super().__init__(f"Workflow not found: {workflow_id}", {"workflow_id": workflow_id})
        self.workflow_id = workflow_id


class TaskError(ClientError):
    """Error related to task operations."""
    pass


class TaskNotFoundError(TaskError):
    """Task not found."""
    
    def __init__(self, task_id: str, workflow_id: Optional[str] = None):
        details = {"task_id": task_id}
        if workflow_id:
            details["workflow_id"] = workflow_id
        super().__init__(f"Task not found: {task_id}", details)
        self.task_id = task_id
        self.workflow_id = workflow_id


# =============================================================================
# Server Errors
# =============================================================================

class ServerError(LatticeError):
    """Base exception for server-side errors."""
    pass


class OrchestratorError(ServerError):
    """Error in orchestrator operations."""
    pass


class OrchestratorNotInitializedError(OrchestratorError):
    """Orchestrator not initialized."""
    
    def __init__(self):
        super().__init__("Orchestrator not initialized. Call initialize() first.")


class SchedulerError(ServerError):
    """Error in scheduler operations."""
    pass


class ResourceError(ServerError):
    """Error related to resource management."""
    pass


class NodeNotFoundError(ResourceError):
    """Node not found in cluster."""
    
    def __init__(self, node_id: str):
        super().__init__(f"Node not found: {node_id}", {"node_id": node_id})
        self.node_id = node_id


class InsufficientResourcesError(ResourceError):
    """Not enough resources available."""
    
    def __init__(self, required: Dict[str, Any], available: Dict[str, Any]):
        super().__init__(
            "Insufficient resources available",
            {"required": required, "available": available}
        )
        self.required = required
        self.available = available


# =============================================================================
# Executor Errors
# =============================================================================

class ExecutorError(LatticeError):
    """Base exception for executor errors."""
    pass


class TaskExecutionError(ExecutorError):
    """Error during task execution."""
    
    def __init__(self, task_id: str, cause: Optional[str] = None):
        message = f"Task execution failed: {task_id}"
        if cause:
            message = f"{message} - {cause}"
        super().__init__(message, {"task_id": task_id, "cause": cause})
        self.task_id = task_id
        self.cause = cause


class TaskCancelledError(ExecutorError):
    """Task was cancelled."""
    
    def __init__(self, task_id_or_message: str = "", task_id: str = None):
        if task_id is not None:
            super().__init__(f"Task cancelled: {task_id}", {"task_id": task_id})
            self.task_id = task_id
        else:
            super().__init__(f"Task cancelled: {task_id_or_message}", {"task_id": task_id_or_message})
            self.task_id = task_id_or_message


class TaskTimeoutError(ExecutorError):
    """Task execution timed out."""
    
    def __init__(self, task_id: str, timeout_seconds: int):
        super().__init__(
            f"Task timed out after {timeout_seconds}s: {task_id}",
            {"task_id": task_id, "timeout_seconds": timeout_seconds}
        )
        self.task_id = task_id
        self.timeout_seconds = timeout_seconds


class NodeFailedError(ExecutorError):
    """Node failed during task execution."""
    
    def __init__(self, node_id_or_message: str = "", node_id: str = None, task_id: str = None):
        if node_id is not None:
            details = {"node_id": node_id}
            if task_id:
                details["task_id"] = task_id
            super().__init__(f"Node failed: {node_id}", details)
            self.node_id = node_id
            self.task_id = task_id
        else:
            super().__init__(f"Node failed: {node_id_or_message}", {"node_id": node_id_or_message})
            self.node_id = node_id_or_message
            self.task_id = None


# =============================================================================
# Sandbox Errors
# =============================================================================

class SandboxError(ExecutorError):
    """Base exception for sandbox errors."""
    pass


class SandboxTimeoutError(SandboxError):
    """Sandbox execution timed out."""
    
    def __init__(self, timeout_seconds: int):
        super().__init__(
            f"Sandbox execution timed out after {timeout_seconds}s",
            {"timeout_seconds": timeout_seconds}
        )
        self.timeout_seconds = timeout_seconds


class SandboxResourceLimitError(SandboxError):
    """Sandbox resource limit exceeded."""
    
    def __init__(self, resource_type: str, limit: Any):
        super().__init__(
            f"Resource limit exceeded: {resource_type}",
            {"resource_type": resource_type, "limit": limit}
        )
        self.resource_type = resource_type
        self.limit = limit


class SandboxSecurityError(SandboxError):
    """Sandbox security violation."""
    
    def __init__(self, violation: str):
        super().__init__(f"Security violation: {violation}", {"violation": violation})
        self.violation = violation


# =============================================================================
# Validation Errors
# =============================================================================

class ValidationError(LatticeError):
    """Base exception for validation errors."""
    pass


class InvalidTaskDefinitionError(ValidationError):
    """Invalid task definition."""
    
    def __init__(self, reason: str):
        super().__init__(f"Invalid task definition: {reason}", {"reason": reason})
        self.reason = reason


class InvalidWorkflowError(ValidationError):
    """Invalid workflow definition."""
    
    def __init__(self, reason: str, workflow_id: Optional[str] = None):
        details = {"reason": reason}
        if workflow_id:
            details["workflow_id"] = workflow_id
        super().__init__(f"Invalid workflow: {reason}", details)
        self.reason = reason
        self.workflow_id = workflow_id


class CyclicDependencyError(ValidationError):
    """Cyclic dependency detected in workflow."""
    
    def __init__(self, cycle: Optional[list] = None):
        super().__init__(
            "Cyclic dependency detected in workflow",
            {"cycle": cycle} if cycle else {}
        )
        self.cycle = cycle
