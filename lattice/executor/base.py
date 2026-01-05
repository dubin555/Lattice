"""
Abstract base class for task executors.
Supports multiple backends: Ray, Local (concurrent.futures), etc.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from lattice.exceptions import (
    TaskExecutionError as TaskError,
    TaskCancelledError,
    NodeFailedError,
)


class ExecutorType(Enum):
    RAY = "ray"
    LOCAL = "local"


@dataclass
class TaskSubmission:
    func: Callable
    args: tuple = ()
    kwargs: Dict[str, Any] = None
    resources: Dict[str, Any] = None
    node_id: Optional[str] = None
    gpu_id: Optional[int] = None

    def __post_init__(self):
        if self.kwargs is None:
            self.kwargs = {}
        if self.resources is None:
            self.resources = {}


@dataclass
class TaskHandle:
    handle_id: Any
    executor_type: ExecutorType


class ExecutorBackend(ABC):
    @abstractmethod
    def initialize(self) -> None:
        """Initialize the executor backend."""
        pass

    @abstractmethod
    def submit(self, submission: TaskSubmission) -> TaskHandle:
        """Submit a task for execution."""
        pass

    @abstractmethod
    def get_result(self, handle: TaskHandle) -> Any:
        """Get the result of a completed task (blocking)."""
        pass

    @abstractmethod
    def wait(self, handles: List[TaskHandle], timeout: float = 0) -> tuple[List[TaskHandle], List[TaskHandle]]:
        """Wait for tasks to complete. Returns (done, pending)."""
        pass

    @abstractmethod
    def cancel(self, handle: TaskHandle) -> bool:
        """Cancel a running task."""
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """Shutdown the executor backend."""
        pass

    @abstractmethod
    def get_available_resources(self) -> Dict[str, Any]:
        """Get available resources (CPU, GPU, memory)."""
        pass


__all__ = [
    "ExecutorType",
    "TaskSubmission",
    "TaskHandle",
    "ExecutorBackend",
    "TaskError",
    "TaskCancelledError",
    "NodeFailedError",
]
