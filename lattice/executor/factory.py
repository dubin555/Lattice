"""
Executor factory for creating executor backends.
"""
from typing import Optional

from lattice.executor.base import ExecutorBackend, ExecutorType


def create_executor(
    executor_type: ExecutorType = ExecutorType.RAY,
    **kwargs,
) -> ExecutorBackend:
    if executor_type == ExecutorType.RAY:
        from lattice.executor.ray_executor import RayExecutor
        return RayExecutor(**kwargs)
    elif executor_type == ExecutorType.LOCAL:
        from lattice.executor.local_executor import LocalExecutor
        return LocalExecutor(**kwargs)
    else:
        raise ValueError(f"Unknown executor type: {executor_type}")
