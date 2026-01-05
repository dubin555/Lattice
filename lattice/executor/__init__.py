"""
Executor module for Lattice task execution.
Supports multiple backends: Ray, Local.
"""
from lattice.executor.base import (
    ExecutorBackend,
    ExecutorType,
    TaskSubmission,
    TaskHandle,
    TaskError,
    TaskCancelledError,
    NodeFailedError,
)
from lattice.executor.factory import create_executor

def __getattr__(name):
    if name in ("execute_code_task", "execute_langgraph_task", "CodeRunner", "TaskExecutor"):
        from lattice.executor.runner import (
            execute_code_task,
            execute_langgraph_task,
            CodeRunner,
            TaskExecutor,
        )
        return locals()[name]
    if name == "RayExecutor":
        from lattice.executor.ray_executor import RayExecutor
        return RayExecutor
    if name == "LocalExecutor":
        from lattice.executor.local_executor import LocalExecutor
        return LocalExecutor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "ExecutorBackend",
    "ExecutorType",
    "TaskSubmission",
    "TaskHandle",
    "TaskError",
    "TaskCancelledError",
    "NodeFailedError",
    "create_executor",
    "RayExecutor",
    "LocalExecutor",
    "execute_code_task",
    "execute_langgraph_task",
    "CodeRunner",
    "TaskExecutor",
]
