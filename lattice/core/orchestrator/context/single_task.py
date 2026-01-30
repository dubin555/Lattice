"""
SingleTaskContext for tracking single task execution.
"""
import asyncio
from typing import Dict, Any

from lattice.core.orchestrator.context.base import BaseContext
from lattice.exceptions import BackpressureError


class SingleTaskContext(BaseContext):
    """Context for tracking single task execution."""

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.result_queue: asyncio.Queue = asyncio.Queue()

    async def on_task_finished(self, msg_data: Dict[str, Any]) -> None:
        """Handle task completion."""
        await self.result_queue.put(msg_data.get("result"))

    async def on_task_started(self, msg_data: Dict[str, Any]) -> None:
        """Handle task start notification."""
        pass

    async def on_task_exception(self, msg_data: Dict[str, Any]) -> None:
        """Handle task exception."""
        await self.result_queue.put(msg_data.get("result"))

    async def on_task_rejected(self, msg_data: Dict[str, Any]) -> None:
        """Handle task rejection due to backpressure.

        For single task context, we raise a BackpressureError to signal
        that the system cannot accept more work.
        """
        error = BackpressureError(
            message=f"Task {self.task_id} rejected due to backpressure",
            queue_name="pending_tasks",
            current_size=msg_data.get("pending_count"),
            capacity=msg_data.get("max_pending"),
        )
        await self.result_queue.put(error)

    async def wait_result(self) -> Any:
        """Wait for the task result."""
        result = await self.result_queue.get()
        if isinstance(result, Exception):
            raise result
        return result
