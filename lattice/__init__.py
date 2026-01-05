"""
Lattice - Task-level distributed framework for LLM agents.
"""
from lattice.client import (
    LatticeClient,
    LatticeWorkflow,
    LatticeTask,
    TaskOutput,
    task,
    get_task_metadata,
    LangGraphClient,
)

__version__ = "2.0.0"

__all__ = [
    "LatticeClient",
    "LatticeWorkflow",
    "LatticeTask",
    "TaskOutput",
    "task",
    "get_task_metadata",
    "LangGraphClient",
]
