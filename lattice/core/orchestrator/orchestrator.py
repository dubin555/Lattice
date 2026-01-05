"""
Workflow orchestrator for managing workflow execution.
Simplified to focus on API layer and workflow definitions.
"""
import asyncio
import copy
import logging
import multiprocessing as mp
import uuid
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union

from lattice.core.scheduler.message_bus import Message, MessageType, MessageBus
from lattice.core.scheduler.scheduler import run_scheduler_process
from lattice.core.workflow.base import Workflow, LangGraphWorkflow, CodeTask, LangGraphTask

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
    def __init__(self, ray_head_port: int = 6379):
        self._ray_head_port = ray_head_port
        self._message_bus: Optional[MessageBus] = None
        self._scheduler_process: Optional[mp.Process] = None
        self._lock = asyncio.Lock()
        
        self._workflows: Dict[str, Union[Workflow, LangGraphWorkflow]] = {}
        self._run_contexts: Dict[str, "RunContext"] = {}
        
        self._monitor_task: Optional[asyncio.Task] = None

    @property
    def ray_head_port(self) -> int:
        return self._ray_head_port

    def initialize(self) -> None:
        self._message_bus = MessageBus()
        
        self._scheduler_process = mp.Process(
            target=run_scheduler_process,
            args=(self._message_bus, self._ray_head_port),
        )
        self._scheduler_process.start()
        
        if not self._message_bus.wait_ready(timeout=60):
            raise RuntimeError("Scheduler failed to start")
        
        logger.info("Orchestrator initialized")

    async def start_monitor(self) -> None:
        self._monitor_task = asyncio.create_task(self._monitor_loop())

    async def _monitor_loop(self) -> None:
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
        workflow = Workflow(workflow_id)
        self._workflows[workflow_id] = workflow
        return workflow

    def get_workflow(self, workflow_id: str) -> Optional[Union[Workflow, LangGraphWorkflow]]:
        return self._workflows.get(workflow_id)

    def get_workflow_tasks(self, workflow_id: str) -> List[Dict[str, str]]:
        workflow = self._workflows.get(workflow_id)
        if workflow is None:
            return []
        return workflow.get_task_info_list()

    def run_workflow(self, workflow_id: str) -> str:
        workflow = self._workflows.get(workflow_id)
        if workflow is None:
            raise ValueError(f"Workflow {workflow_id} not found")

        run_id = str(uuid.uuid4())
        submitted_workflow = copy.deepcopy(workflow)
        
        ctx = RunContext(run_id, submitted_workflow, self._message_bus)
        self._run_contexts[run_id] = ctx
        ctx.submit_start_tasks()

        return run_id

    async def get_workflow_results(self, run_id: str) -> asyncio.Queue:
        ctx = self._run_contexts.get(run_id)
        if ctx is None:
            raise ValueError(f"Run {run_id} not found")
        return ctx.result_queue

    async def wait_workflow_complete(self, run_id: str) -> List[Dict[str, Any]]:
        ctx = self._run_contexts.get(run_id)
        if ctx is None:
            raise ValueError(f"Run {run_id} not found")

        results = await ctx.wait_complete()
        
        self._message_bus.send_to_scheduler(Message(
            message_type=MessageType.CLEAR_WORKFLOW,
            data={"workflow_id": run_id},
        ))

        return results

    async def stop_workflow(self, run_id: str) -> None:
        async with self._lock:
            if run_id in self._run_contexts:
                del self._run_contexts[run_id]

        self._message_bus.send_to_scheduler(Message(
            message_type=MessageType.STOP_WORKFLOW,
            data={"workflow_id": run_id},
        ))

    def add_worker(self, node_ip: str, node_id: str, resources: Dict[str, Any]) -> None:
        self._message_bus.send_to_scheduler(Message(
            message_type=MessageType.START_WORKER,
            data={
                "node_ip": node_ip,
                "node_id": node_id,
                "resources": resources,
            },
        ))

    def remove_worker(self, node_id: str) -> None:
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
        logger.info("Orchestrator cleanup")
        
        if self._message_bus:
            self._message_bus.send_to_scheduler(Message(
                message_type=MessageType.SHUTDOWN,
                data={},
            ))

        if self._scheduler_process and self._scheduler_process.is_alive():
            self._scheduler_process.join(timeout=5)
            if self._scheduler_process.is_alive():
                self._scheduler_process.terminate()

        if self._message_bus:
            self._message_bus.close()


class RunContext(BaseContext):
    """Context for tracking workflow execution."""
    
    def __init__(self, run_id: str, workflow: Workflow, message_bus: MessageBus):
        self.run_id = run_id
        self.workflow = workflow
        self.message_bus = message_bus
        self.result_queue: asyncio.Queue = asyncio.Queue()
        self.completed_count = 0

    def submit_start_tasks(self) -> None:
        start_tasks = self.workflow.get_start_tasks()
        for task in start_tasks:
            task_data = task.to_dict()
            task_data["workflow_id"] = self.run_id
            self.message_bus.send_to_scheduler(Message(
                message_type=MessageType.RUN_TASK,
                data=task_data,
            ))

    async def on_task_finished(self, msg_data: Dict[str, Any]) -> None:
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
        await self.result_queue.put({
            "type": MessageType.START_TASK.value,
            "data": msg_data,
        })

    async def on_task_exception(self, msg_data: Dict[str, Any]) -> None:
        await self.result_queue.put({
            "type": MessageType.TASK_EXCEPTION.value,
            "data": msg_data,
        })

    async def on_llm_instance_ready(self, msg_data: Dict[str, Any]) -> None:
        pass

    async def wait_complete(self) -> List[Dict[str, Any]]:
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
        await self.result_queue.put(msg_data.get("result"))

    async def on_task_started(self, msg_data: Dict[str, Any]) -> None:
        pass

    async def on_task_exception(self, msg_data: Dict[str, Any]) -> None:
        await self.result_queue.put(msg_data.get("result"))

    async def on_llm_instance_ready(self, msg_data: Dict[str, Any]) -> None:
        pass

    async def wait_result(self) -> Any:
        return await self.result_queue.get()
