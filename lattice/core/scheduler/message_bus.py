"""
Message bus for inter-thread communication.
Uses Python queue.Queue for thread-safe message passing.
"""
import queue
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional
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
    """Thread-safe message bus for communication between Orchestrator and Scheduler."""

    def __init__(self):
        self._to_scheduler: queue.Queue = queue.Queue()
        self._from_scheduler: queue.Queue = queue.Queue()
        self._ready_event: threading.Event = threading.Event()

    @property
    def to_scheduler_queue(self) -> queue.Queue:
        return self._to_scheduler

    @property
    def from_scheduler_queue(self) -> queue.Queue:
        return self._from_scheduler

    def send_to_scheduler(self, message: Message) -> None:
        """Send a message to the scheduler thread."""
        self._to_scheduler.put(message)

    def receive_from_scheduler(self, timeout: Optional[float] = None) -> Optional[Message]:
        """Receive a message from the scheduler thread."""
        try:
            return self._from_scheduler.get(timeout=timeout)
        except queue.Empty:
            return None

    def send_from_scheduler(self, message: Message) -> None:
        """Send a message from the scheduler thread."""
        self._from_scheduler.put(message)

    def receive_in_scheduler(self, timeout: Optional[float] = None) -> Optional[Message]:
        """Receive a message in the scheduler thread."""
        try:
            return self._to_scheduler.get(timeout=timeout)
        except queue.Empty:
            return None

    def signal_ready(self) -> None:
        """Signal that the scheduler is ready."""
        self._ready_event.set()

    def wait_ready(self, timeout: Optional[float] = None) -> bool:
        """Wait for the scheduler to be ready."""
        return self._ready_event.wait(timeout=timeout)

    def close(self) -> None:
        """Clean up resources."""
        # queue.Queue doesn't need explicit closing
        pass
