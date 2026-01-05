"""
Message bus for inter-process communication.
Replaces ZeroMQ with Python multiprocessing queues.
"""
import multiprocessing as mp
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional
from queue import Empty
import logging

logger = logging.getLogger(__name__)


class MessageType(Enum):
    RUN_TASK = "run_task"
    START_TASK = "start_task"
    FINISH_TASK = "finish_task"
    TASK_EXCEPTION = "task_exception"
    
    CLEAR_WORKFLOW = "clear_workflow"
    STOP_WORKFLOW = "stop_workflow"
    FINISH_WORKFLOW = "finish_workflow"
    
    START_WORKER = "start_worker"
    STOP_WORKER = "stop_worker"
    
    START_LLM_INSTANCE = "start_llm_instance"
    STOP_LLM_INSTANCE = "stop_llm_instance"
    FINISH_LLM_INSTANCE_LAUNCH = "finish_llm_instance_launch"
    
    SHUTDOWN = "shutdown"


@dataclass
class Message:
    message_type: MessageType
    data: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.message_type.value,
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        message_type = MessageType(data["type"])
        return cls(message_type=message_type, data=data.get("data", {}))


class MessageBus:
    def __init__(self):
        self._to_scheduler: mp.Queue = mp.Queue()
        self._from_scheduler: mp.Queue = mp.Queue()
        self._ready_queue: mp.Queue = mp.Queue()

    @property
    def to_scheduler_queue(self) -> mp.Queue:
        return self._to_scheduler

    @property
    def from_scheduler_queue(self) -> mp.Queue:
        return self._from_scheduler

    @property
    def ready_queue(self) -> mp.Queue:
        return self._ready_queue

    def send_to_scheduler(self, message: Message) -> None:
        self._to_scheduler.put(message)

    def receive_from_scheduler(self, timeout: Optional[float] = None) -> Optional[Message]:
        try:
            return self._from_scheduler.get(timeout=timeout)
        except Empty:
            return None

    def send_from_scheduler(self, message: Message) -> None:
        self._from_scheduler.put(message)

    def receive_in_scheduler(self, timeout: Optional[float] = None) -> Optional[Message]:
        try:
            return self._to_scheduler.get(timeout=timeout)
        except Empty:
            return None

    def signal_ready(self) -> None:
        self._ready_queue.put("ready")

    def wait_ready(self, timeout: Optional[float] = None) -> bool:
        try:
            msg = self._ready_queue.get(timeout=timeout)
            return msg == "ready"
        except Empty:
            return False

    def close(self) -> None:
        self._to_scheduler.close()
        self._from_scheduler.close()
        self._ready_queue.close()
