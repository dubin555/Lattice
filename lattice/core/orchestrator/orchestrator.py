"""
Workflow orchestrator for managing workflow execution.
Simplified to focus on API layer and workflow definitions.
"""
import asyncio
import copy
import logging
import time
import uuid
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union

from lattice.core.scheduler.message_bus import Message, MessageType, MessageBus
from lattice.core.scheduler.scheduler import Scheduler
from lattice.core.workflow.base import Workflow, LangGraphWorkflow, CodeTask, LangGraphTask

# Import metrics - optional dependency
try:
    from lattice.observability.metrics import (
        record_workflow_created,
        record_workflow_started,
        record_workflow_completed,
        record_workflow_failed,
    )
    METRICS_ENABLED = True
except ImportError:
    METRICS_ENABLED = False

logger = logging.getLogger(__name__)


class BaseContext(ABC):
    """Base class for workflow/task execution contexts."""

    @abstractmethod
    async def on_task_finished(self, msg_data: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    async def on_task_started(self, msg_data: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    async def on_task_exception(self, msg_data: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    async def on_llm_instance_ready(self, msg_data: Dict[str, Any]) -> None:
        pass


class Orchestrator:
    """
    Workflow orchestrator that manages workflow execution.

    The Orchestrator runs in the main thread and communicates with the
    Scheduler (running in a background thread) via MessageBus.
    """

    def __init__(self, ray_head_port: int = 6379):
        self._ray_head_port = ray_head_port
        self._message_bus: Optional[MessageBus] = None
        self._scheduler: Optional[Scheduler] = None
        self._lock = asyncio.Lock()

        self._workflows: Dict[str, Union[Workflow, LangGraphWorkflow]] = {}
        self._run_contexts: Dict[str, "RunContext"] = {}
        self._workflow_start_times: Dict[str, float] = {}

        self._monitor_task: Optional[asyncio.Task] = None

    @property
    def ray_head_port(self) -> int:
        return self._ray_head_port

    def initialize(self) -> None:
        """Initialize the orchestrator and start the scheduler thread."""
        self._message_bus = MessageBus()

        # Create and start scheduler in a background thread
        self._scheduler = Scheduler(
            message_bus=self._message_bus,
            ray_head_port=self._ray_head_port,
        )
        self._scheduler.start()

        # Wait for scheduler to be ready
        if not self._message_bus.wait_ready(timeout=60):
            raise RuntimeError("Scheduler failed to start")

        logger.info("Orchestrator initialized")

    async def start_monitor(self) -> None:
        """Start the message monitor loop."""
        self._monitor_task = asyncio.create_task(self._monitor_loop())

    async def _monitor_loop(self) -> None:
        """Monitor loop for receiving messages from the scheduler."""
        while True:
            try:
                message = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self._message_bus.receive_from_scheduler(timeout=0.1),
                )

                if message is None:
                    await asyncio.sleep(0.01)
                    continue

                await self._handle_scheduler_message(message)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")

    async def _handle_scheduler_message(self, message: Message) -> None:
        """Handle messages received from the scheduler."""
        msg_type = message.message_type
        msg_data = message.data

        workflow_id = msg_data.get("workflow_id")
        task_id = msg_data.get("task_id")

        async with self._lock:
            ctx = self._run_contexts.get(workflow_id) or self._run_contexts.get(task_id)
            if ctx is None:
                return

            if msg_type == MessageType.FINISH_TASK:
                await ctx.on_task_finished(msg_data)
            elif msg_type == MessageType.START_TASK:
                await ctx.on_task_started(msg_data)
            elif msg_type == MessageType.TASK_EXCEPTION:
                await ctx.on_task_exception(msg_data)
            elif msg_type == MessageType.FINISH_LLM_INSTANCE_LAUNCH:
                await ctx.on_llm_instance_ready(msg_data)

    def create_workflow(self, workflow_id: str) -> Workflow:
        """Create a new workflow."""
        workflow = Workflow(workflow_id)
        self._workflows[workflow_id] = workflow

        if METRICS_ENABLED:
            record_workflow_created()

        return workflow

    def get_workflow(self, workflow_id: str) -> Optional[Union[Workflow, LangGraphWorkflow]]:
        """Get a workflow by ID."""
        return self._workflows.get(workflow_id)

    def get_workflow_tasks(self, workflow_id: str) -> List[Dict[str, str]]:
        """Get task info list for a workflow."""
        workflow = self._workflows.get(workflow_id)
        if workflow is None:
            return []
        return workflow.get_task_info_list()

    def run_workflow(self, workflow_id: str) -> str:
        """Run a workflow and return the run ID."""
        workflow = self._workflows.get(workflow_id)
        if workflow is None:
            raise ValueError(f"Workflow {workflow_id} not found")

        run_id = str(uuid.uuid4())
        submitted_workflow = copy.deepcopy(workflow)

        ctx = RunContext(run_id, submitted_workflow, self._message_bus)
        self._run_contexts[run_id] = ctx
        self._workflow_start_times[run_id] = time.time()
        ctx.submit_start_tasks()

        if METRICS_ENABLED:
            record_workflow_started()

        return run_id

    async def get_workflow_results(self, run_id: str) -> asyncio.Queue:
        """Get the result queue for a workflow run."""
        ctx = self._run_contexts.get(run_id)
        if ctx is None:
            raise ValueError(f"Run {run_id} not found")
        return ctx.result_queue

    async def wait_workflow_complete(self, run_id: str) -> List[Dict[str, Any]]:
        """Wait for a workflow to complete and return results."""
        ctx = self._run_contexts.get(run_id)
        if ctx is None:
            raise ValueError(f"Run {run_id} not found")

        results = await ctx.wait_complete()

        if METRICS_ENABLED:
            start_time = self._workflow_start_times.pop(run_id, None)
            if start_time:
                duration = time.time() - start_time
                if results and results[-1].get("type") == MessageType.TASK_EXCEPTION.value:
                    record_workflow_failed(duration)
                else:
                    record_workflow_completed(duration)

        self._message_bus.send_to_scheduler(Message(
            message_type=MessageType.CLEAR_WORKFLOW,
            data={"workflow_id": run_id},
        ))

        return results

    async def stop_workflow(self, run_id: str) -> None:
        """Stop a running workflow."""
        async with self._lock:
            if run_id in self._run_contexts:
                del self._run_contexts[run_id]

        if METRICS_ENABLED:
            start_time = self._workflow_start_times.pop(run_id, None)
            if start_time:
                duration = time.time() - start_time
                record_workflow_failed(duration)

        self._message_bus.send_to_scheduler(Message(
            message_type=MessageType.STOP_WORKFLOW,
            data={"workflow_id": run_id},
        ))

    def add_worker(self, node_ip: str, node_id: str, resources: Dict[str, Any]) -> None:
        """Register a worker node."""
        self._message_bus.send_to_scheduler(Message(
            message_type=MessageType.START_WORKER,
            data={
                "node_ip": node_ip,
                "node_id": node_id,
                "resources": resources,
            },
        ))

    def remove_worker(self, node_id: str) -> None:
        """Remove a worker node."""
        self._message_bus.send_to_scheduler(Message(
            message_type=MessageType.STOP_WORKER,
            data={"node_id": node_id},
        ))

    async def run_langgraph_task(
        self,
        workflow_id: str,
        task_id: str,
        serialized_args: str,
        serialized_kwargs: str,
    ) -> Any:
        """Run a single LangGraph task."""
        workflow = self._workflows.get(workflow_id)
        if workflow is None or not isinstance(workflow, LangGraphWorkflow):
            raise ValueError(f"LangGraph workflow {workflow_id} not found")

        task = workflow.get_task(task_id)
        if task is None:
            raise ValueError(f"Task {task_id} not found")

        task.set_args(serialized_args)
        task.set_kwargs(serialized_kwargs)

        ctx = SingleTaskContext(task_id)
        self._run_contexts[task_id] = ctx

        self._message_bus.send_to_scheduler(Message(
            message_type=MessageType.RUN_TASK,
            data=task.to_dict(),
        ))

        result = await ctx.wait_result()
        del self._run_contexts[task_id]
        return result

    def cleanup(self) -> None:
        """Clean up resources and stop the scheduler."""
        logger.info("Orchestrator cleanup")

        # Send shutdown signal to scheduler
        if self._message_bus:
            self._message_bus.send_to_scheduler(Message(
                message_type=MessageType.SHUTDOWN,
                data={},
            ))

        # Stop the scheduler thread
        if self._scheduler:
            self._scheduler.stop()

        # Close message bus
        if self._message_bus:
            self._message_bus.close()

        logger.info("Orchestrator cleanup complete")


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

    async def on_llm_instance_ready(self, msg_data: Dict[str, Any]) -> None:
        """Handle LLM instance ready notification."""
        pass

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

    async def on_llm_instance_ready(self, msg_data: Dict[str, Any]) -> None:
        """Handle LLM instance ready notification."""
        pass

    async def wait_result(self) -> Any:
        """Wait for the task result."""
        return await self.result_queue.get()
