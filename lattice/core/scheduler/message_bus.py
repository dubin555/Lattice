"""
Message bus for inter-thread communication.
Uses Python queue.Queue for thread-safe message passing with backpressure support.
"""
import queue
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Default queue capacity limits
DEFAULT_TO_SCHEDULER_CAPACITY = 10000
DEFAULT_FROM_SCHEDULER_CAPACITY = 10000


class MessageType(Enum):
    RUN_TASK = "run_task"
    START_TASK = "start_task"
    FINISH_TASK = "finish_task"
    TASK_EXCEPTION = "task_exception"
    TASK_REJECTED = "task_rejected"  # Backpressure: task was rejected due to capacity limits

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
    """Thread-safe message bus with backpressure support.

    Provides bounded queues for communication between Orchestrator and Scheduler.
    When queues reach capacity, sends will fail with appropriate signals for
    backpressure handling.
    """

    def __init__(
        self,
        to_scheduler_capacity: int = DEFAULT_TO_SCHEDULER_CAPACITY,
        from_scheduler_capacity: int = DEFAULT_FROM_SCHEDULER_CAPACITY,
    ):
        """Initialize the message bus with bounded queues.

        Args:
            to_scheduler_capacity: Maximum messages in to-scheduler queue.
            from_scheduler_capacity: Maximum messages in from-scheduler queue.
        """
        self._to_scheduler: queue.Queue = queue.Queue(maxsize=to_scheduler_capacity)
        self._from_scheduler: queue.Queue = queue.Queue(maxsize=from_scheduler_capacity)
        self._ready_event: threading.Event = threading.Event()
        self._to_scheduler_capacity = to_scheduler_capacity
        self._from_scheduler_capacity = from_scheduler_capacity

    @property
    def to_scheduler_queue(self) -> queue.Queue:
        return self._to_scheduler

    @property
    def from_scheduler_queue(self) -> queue.Queue:
        return self._from_scheduler

    @property
    def to_scheduler_size(self) -> int:
        """Current number of messages in the to-scheduler queue."""
        return self._to_scheduler.qsize()

    @property
    def from_scheduler_size(self) -> int:
        """Current number of messages in the from-scheduler queue."""
        return self._from_scheduler.qsize()

    def is_to_scheduler_full(self) -> bool:
        """Check if the to-scheduler queue is at capacity."""
        return self._to_scheduler.full()

    def is_from_scheduler_full(self) -> bool:
        """Check if the from-scheduler queue is at capacity."""
        return self._from_scheduler.full()

    def send_to_scheduler(self, message: Message, block: bool = True, timeout: Optional[float] = None) -> bool:
        """Send a message to the scheduler thread.

        Args:
            message: The message to send.
            block: If True, block until space is available. If False, return immediately.
            timeout: Maximum time to wait if blocking (None = wait forever).

        Returns:
            True if the message was sent, False if queue is full (non-blocking mode).

        Raises:
            BackpressureError: If blocking mode times out or queue is full.
        """
        try:
            self._to_scheduler.put(message, block=block, timeout=timeout)
            return True
        except queue.Full:
            logger.warning(
                f"To-scheduler queue is full ({self._to_scheduler_capacity} messages), "
                f"message type: {message.message_type.value}"
            )
            return False

    def try_send_to_scheduler(self, message: Message) -> bool:
        """Try to send a message without blocking.

        Returns:
            True if sent successfully, False if queue is full.
        """
        return self.send_to_scheduler(message, block=False)

    def receive_from_scheduler(self, timeout: Optional[float] = None) -> Optional[Message]:
        """Receive a message from the scheduler thread."""
        try:
            return self._from_scheduler.get(timeout=timeout)
        except queue.Empty:
            return None

    def send_from_scheduler(self, message: Message, block: bool = True, timeout: Optional[float] = None) -> bool:
        """Send a message from the scheduler thread.

        Args:
            message: The message to send.
            block: If True, block until space is available.
            timeout: Maximum time to wait if blocking.

        Returns:
            True if sent, False if queue is full.
        """
        try:
            self._from_scheduler.put(message, block=block, timeout=timeout)
            return True
        except queue.Full:
            logger.warning(
                f"From-scheduler queue is full ({self._from_scheduler_capacity} messages), "
                f"message type: {message.message_type.value}"
            )
            return False

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

    def get_backpressure_status(self) -> Dict[str, Any]:
        """Get current backpressure status for monitoring.

        Returns:
            Dictionary with queue sizes and capacity info.
        """
        return {
            "to_scheduler_size": self.to_scheduler_size,
            "to_scheduler_capacity": self._to_scheduler_capacity,
            "to_scheduler_utilization": self.to_scheduler_size / self._to_scheduler_capacity,
            "from_scheduler_size": self.from_scheduler_size,
            "from_scheduler_capacity": self._from_scheduler_capacity,
            "from_scheduler_utilization": self.from_scheduler_size / self._from_scheduler_capacity,
            "is_to_scheduler_full": self.is_to_scheduler_full(),
            "is_from_scheduler_full": self.is_from_scheduler_full(),
        }
