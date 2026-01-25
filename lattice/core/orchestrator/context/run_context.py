"""
RunContext for tracking workflow execution.
"""
import asyncio
from typing import Dict, List, Any

from lattice.core.orchestrator.context.base import BaseContext
from lattice.core.scheduler.message_bus import Message, MessageType, MessageBus
from lattice.core.workflow.base import Workflow


class RunContext(BaseContext):
    """Context for tracking workflow execution."""

    def __init__(self, run_id: str, workflow: Workflow, message_bus: MessageBus):
        self.run_id = run_id
        self.workflow = workflow
        self.message_bus = message_bus
        self.result_queue: asyncio.Queue = asyncio.Queue()
        self.completed_count = 0

    def submit_start_tasks(self) -> None:
        """Submit initial tasks that have no dependencies."""
        start_tasks = self.workflow.get_start_tasks()
        for task in start_tasks:
            task_data = task.to_dict()
            task_data["workflow_id"] = self.run_id
            self.message_bus.send_to_scheduler(Message(
                message_type=MessageType.RUN_TASK,
                data=task_data,
            ))

    async def on_task_finished(self, msg_data: Dict[str, Any]) -> None:
        """Handle task completion."""
        await self.result_queue.put({
            "type": MessageType.FINISH_TASK.value,
            "data": msg_data,
        })

        task_id = msg_data.get("task_id")
        ready_tasks = self.workflow.get_ready_tasks_after_completion(task_id)

        for task in ready_tasks:
            task_data = task.to_dict()
            task_data["workflow_id"] = self.run_id
            self.message_bus.send_to_scheduler(Message(
                message_type=MessageType.RUN_TASK,
                data=task_data,
            ))

    async def on_task_started(self, msg_data: Dict[str, Any]) -> None:
        """Handle task start notification."""
        await self.result_queue.put({
            "type": MessageType.START_TASK.value,
            "data": msg_data,
        })

    async def on_task_exception(self, msg_data: Dict[str, Any]) -> None:
        """Handle task exception."""
        await self.result_queue.put({
            "type": MessageType.TASK_EXCEPTION.value,
            "data": msg_data,
        })

    async def wait_complete(self) -> List[Dict[str, Any]]:
        """Wait for the workflow to complete."""
        total_tasks = self.workflow.task_count
        results = []
        completed_count = 0

        while completed_count < total_tasks:
            msg = await self.result_queue.get()
            results.append(msg)

            if msg["type"] == MessageType.FINISH_TASK.value:
                completed_count += 1
            elif msg["type"] == MessageType.TASK_EXCEPTION.value:
                break

        return results
