"""
Core client module for Lattice.
"""
from lattice.client.core.client import LatticeClient
from lattice.client.core.workflow import LatticeWorkflow
from lattice.client.core.models import LatticeTask, TaskOutput, TaskOutputs
from lattice.client.core.decorator import task, get_task_metadata, TaskMetadata, BatchConfig

__all__ = [
    "LatticeClient",
    "LatticeWorkflow",
    "LatticeTask",
    "TaskOutput",
    "TaskOutputs",
    "task",
    "get_task_metadata",
    "TaskMetadata",
    "BatchConfig",
]
