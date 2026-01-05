"""
Task scheduler for distributed task execution.
Single-threaded event loop with pluggable executor backends.

Architecture:
  Orchestrator (API process)
       │
       │ MessageBus (multiprocessing.Queue)
       ▼
  Scheduler (separate process)
       │
       │ ExecutorBackend (Ray / Local / ...)
       ▼
  Workers (execute tasks)
"""
import base64
import logging
import os
from typing import Dict, Any, List, Optional

import cloudpickle

from lattice.core.scheduler.message_bus import Message, MessageType, MessageBus
from lattice.core.resource.manager import ResourceManager, TaskResourceRequirements
from lattice.core.resource.node import SelectedNode
from lattice.core.runtime.task import (
    BaseTaskRuntime,
    CodeTaskRuntime,
    LangGraphTaskRuntime,
    create_task_runtime,
)
from lattice.core.runtime.workflow import WorkflowRuntimeManager
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

logger = logging.getLogger(__name__)

LOOP_INTERVAL = 0.05


def _deserialize_and_call(serialized_code: str, serialized_args: str, serialized_kwargs: str):
    func = cloudpickle.loads(base64.b64decode(serialized_code))
    args = cloudpickle.loads(base64.b64decode(serialized_args))
    kwargs = cloudpickle.loads(base64.b64decode(serialized_kwargs))
    return func(*args, **kwargs)


def _run_code_task(code_str: Optional[str], serialized_code: Optional[str], task_input_data: Dict[str, Any]):
    if serialized_code is not None:
        func = cloudpickle.loads(base64.b64decode(serialized_code))
        return func(task_input_data)
    elif code_str is not None:
        from lattice.executor.runner import CodeRunner
        return CodeRunner(code_str, task_input_data).run()
    else:
        raise ValueError("Either code_str or serialized_code must be provided")


class Scheduler:
    def __init__(
        self,
        message_bus: MessageBus,
        executor_type: ExecutorType = ExecutorType.RAY,
        ray_head_port: int = 6379,
    ):
        self._message_bus = message_bus
        self._executor_type = executor_type
        self._ray_head_port = ray_head_port
        
        self._executor: Optional[ExecutorBackend] = None
        self._workflow_manager = WorkflowRuntimeManager()
        self._resource_manager = ResourceManager()
        self._pending_tasks: List[BaseTaskRuntime] = []
        self._task_handles: Dict[str, TaskHandle] = {}
        self._handle_to_task: Dict[Any, str] = {}
        self._running = False

    def start(self) -> None:
        self._running = True
        self._init_executor()
        self._message_bus.signal_ready()
        logger.info(f"Scheduler started with {self._executor_type.value} executor")
        self._run_loop()

    def _init_executor(self) -> None:
        if self._executor_type == ExecutorType.RAY:
            self._executor = create_executor(
                ExecutorType.RAY,
                ray_head_port=self._ray_head_port,
                start_ray=True,
            )
            self._executor.initialize()
            self._resource_manager.initialize_with_ray()
        else:
            self._executor = create_executor(ExecutorType.LOCAL)
            self._executor.initialize()
            self._resource_manager.initialize_local()

    def _run_loop(self) -> None:
        while self._running:
            msg = self._message_bus.receive_in_scheduler(timeout=LOOP_INTERVAL)
            if msg:
                self._handle_message(msg)
            self._dispatch_pending_tasks()
            self._check_completed_tasks()
            if self._executor_type == ExecutorType.RAY:
                self._resource_manager.check_node_health()

    def _handle_message(self, message: Message) -> None:
        handlers = {
            MessageType.RUN_TASK: lambda d: self._pending_tasks.append(create_task_runtime(d)),
            MessageType.CLEAR_WORKFLOW: lambda d: self._workflow_manager.clear_workflow(d["workflow_id"]),
            MessageType.STOP_WORKFLOW: lambda d: self._cancel_workflow(d["workflow_id"]),
            MessageType.START_WORKER: lambda d: self._resource_manager.add_node(
                node_id=d["node_id"], node_ip=d["node_ip"], resources=d["resources"]
            ),
            MessageType.STOP_WORKER: lambda d: self._resource_manager.remove_node(d["node_id"]),
            MessageType.SHUTDOWN: lambda d: self._cleanup(),
        }
        handler = handlers.get(message.message_type)
        if handler:
            handler(message.data)

    def _dispatch_pending_tasks(self) -> None:
        remaining = []
        for task in self._pending_tasks:
            self._workflow_manager.add_task(task)
            
            if self._executor_type == ExecutorType.LOCAL:
                self._submit_task(task, None)
            else:
                requirements = TaskResourceRequirements.from_dict(task.resources)
                node = self._resource_manager.select_node(requirements)
                if node:
                    self._submit_task(task, node)
                else:
                    remaining.append(task)
        self._pending_tasks = remaining

    def _submit_task(self, task: BaseTaskRuntime, node: Optional[SelectedNode]) -> None:
        try:
            if isinstance(task, LangGraphTaskRuntime):
                submission = TaskSubmission(
                    func=_deserialize_and_call,
                    args=(task.serialized_code, task.serialized_args, task.serialized_kwargs),
                    resources=task.resources,
                    node_id=node.node_id if node else None,
                    gpu_id=node.gpu_id if node else None,
                )
            elif isinstance(task, CodeTaskRuntime):
                task_input_data = self._resolve_inputs(task)
                submission = TaskSubmission(
                    func=_run_code_task,
                    args=(task.code_str, task.serialized_code, task_input_data),
                    resources=task.resources,
                    node_id=node.node_id if node else None,
                    gpu_id=node.gpu_id if node else None,
                )
            else:
                return

            handle = self._executor.submit(submission)
            self._task_handles[task.task_id] = handle
            self._handle_to_task[handle.handle_id] = task.task_id
            self._workflow_manager.run_task(task, handle.handle_id, node)
            
            self._send(MessageType.START_TASK, {
                "workflow_id": task.workflow_id,
                "task_id": task.task_id,
                "node_ip": node.node_ip if node else "local",
                "node_id": node.node_id if node else "local",
                "gpu_id": node.gpu_id if node else None,
            })
        except Exception as e:
            logger.error(f"Failed to submit task {task.task_id}: {e}")

    def _resolve_inputs(self, task: CodeTaskRuntime) -> Dict[str, Any]:
        result = {}
        for _, info in task.task_input.get("input_params", {}).items():
            key, value = info.get("key"), info.get("value")
            if info.get("input_schema") == "from_task":
                value = self._workflow_manager.get_task_result_value(task.workflow_id, value)
            result[key] = value
        return result

    def _check_completed_tasks(self) -> None:
        handles = list(self._task_handles.values())
        if not handles:
            return

        try:
            done, _ = self._executor.wait(handles, timeout=0)
        except Exception:
            return

        for handle in done:
            task_id = self._handle_to_task.get(handle.handle_id)
            if not task_id:
                continue
            workflow = self._workflow_manager.get_workflow_by_task_id(task_id)
            if workflow:
                task_obj = workflow.get_task(task_id)
                if task_obj:
                    self._handle_task_result(task_obj, handle)

    def _handle_task_result(self, task: BaseTaskRuntime, handle: TaskHandle) -> None:
        try:
            result = self._executor.get_result(handle)
            self._workflow_manager.set_task_result(task, result)
            self._release_resources(task)
            self._cleanup_handle(task.task_id, handle)
            self._send(MessageType.FINISH_TASK, {
                "workflow_id": task.workflow_id,
                "task_id": task.task_id,
                "result": result,
            })
        except TaskCancelledError:
            self._cleanup_handle(task.task_id, handle)
        except NodeFailedError:
            self._cleanup_handle(task.task_id, handle)
            task.set_status(task.status.__class__.READY)
            self._pending_tasks.append(task)
        except TaskError as e:
            self._cleanup_handle(task.task_id, handle)
            self._handle_task_failure(task, str(e))

    def _cleanup_handle(self, task_id: str, handle: TaskHandle) -> None:
        if task_id in self._task_handles:
            del self._task_handles[task_id]
        if handle.handle_id in self._handle_to_task:
            del self._handle_to_task[handle.handle_id]

    def _handle_task_failure(self, task: BaseTaskRuntime, error: str) -> None:
        for t in self._workflow_manager.cancel_workflow(task.workflow_id):
            self._release_resources(t)
        self._send(MessageType.TASK_EXCEPTION, {
            "workflow_id": task.workflow_id,
            "task_id": task.task_id,
            "result": f"Task failed: {error}",
        })

    def _cancel_workflow(self, workflow_id: str) -> None:
        for task in self._workflow_manager.cancel_workflow(workflow_id):
            handle = self._task_handles.get(task.task_id)
            if handle:
                self._executor.cancel(handle)
                self._cleanup_handle(task.task_id, handle)
            self._release_resources(task)

    def _release_resources(self, task: BaseTaskRuntime) -> None:
        if task.selected_node and self._executor_type == ExecutorType.RAY:
            self._resource_manager.release_task_resources(
                task.selected_node.node_id,
                TaskResourceRequirements.from_dict(task.resources),
                task.selected_node.gpu_id,
            )

    def _send(self, msg_type: MessageType, data: Dict[str, Any]) -> None:
        self._message_bus.send_from_scheduler(Message(msg_type, data))

    def _cleanup(self) -> None:
        logger.info("Scheduler cleanup")
        self._running = False
        if self._executor:
            self._executor.shutdown()
        os._exit(0)

    def stop(self) -> None:
        self._running = False


def run_scheduler_process(
    message_bus: MessageBus,
    ray_head_port: int = 6379,
    executor_type: ExecutorType = ExecutorType.RAY,
) -> None:
    Scheduler(message_bus, executor_type, ray_head_port).start()
