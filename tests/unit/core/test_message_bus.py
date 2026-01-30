"""
Unit tests for scheduler/message_bus module.
"""
import pytest
from unittest.mock import MagicMock, patch
from lattice.core.scheduler.message_bus import Message, MessageType, MessageBus


class TestMessageType:
    def test_task_types(self):
        assert MessageType.RUN_TASK.value == "run_task"
        assert MessageType.START_TASK.value == "start_task"
        assert MessageType.FINISH_TASK.value == "finish_task"
        assert MessageType.TASK_EXCEPTION.value == "task_exception"

    def test_workflow_types(self):
        assert MessageType.CLEAR_WORKFLOW.value == "clear_workflow"
        assert MessageType.STOP_WORKFLOW.value == "stop_workflow"
        assert MessageType.FINISH_WORKFLOW.value == "finish_workflow"

    def test_worker_types(self):
        assert MessageType.START_WORKER.value == "start_worker"
        assert MessageType.STOP_WORKER.value == "stop_worker"

    def test_llm_instance_types(self):
        assert MessageType.START_LLM_INSTANCE.value == "start_llm_instance"
        assert MessageType.STOP_LLM_INSTANCE.value == "stop_llm_instance"
        assert MessageType.FINISH_LLM_INSTANCE_LAUNCH.value == "finish_llm_instance_launch"

    def test_shutdown_type(self):
        assert MessageType.SHUTDOWN.value == "shutdown"


class TestMessage:
    def test_creation(self):
        msg = Message(
            message_type=MessageType.RUN_TASK,
            data={"task_id": "task-1"},
        )
        assert msg.message_type == MessageType.RUN_TASK
        assert msg.data == {"task_id": "task-1"}

    def test_to_dict(self):
        msg = Message(
            message_type=MessageType.FINISH_TASK,
            data={"result": "success"},
        )
        result = msg.to_dict()
        assert result == {
            "type": "finish_task",
            "data": {"result": "success"},
        }

    def test_from_dict(self):
        data = {
            "type": "start_task",
            "data": {"workflow_id": "wf-1"},
        }
        msg = Message.from_dict(data)
        assert msg.message_type == MessageType.START_TASK
        assert msg.data == {"workflow_id": "wf-1"}

    def test_from_dict_empty_data(self):
        data = {"type": "shutdown"}
        msg = Message.from_dict(data)
        assert msg.message_type == MessageType.SHUTDOWN
        assert msg.data == {}

    def test_roundtrip(self):
        original = Message(
            message_type=MessageType.TASK_EXCEPTION,
            data={"error": "Something went wrong", "task_id": "task-123"},
        )
        converted = Message.from_dict(original.to_dict())
        assert converted.message_type == original.message_type
        assert converted.data == original.data


class TestMessageBus:
    def test_creation(self):
        bus = MessageBus()
        assert bus.to_scheduler_queue is not None
        assert bus.from_scheduler_queue is not None

    def test_send_receive_to_scheduler(self):
        bus = MessageBus()
        msg = Message(
            message_type=MessageType.RUN_TASK,
            data={"task_id": "task-1"},
        )
        
        bus.send_to_scheduler(msg)
        received = bus.receive_in_scheduler(timeout=1.0)
        
        assert received is not None
        assert received.message_type == msg.message_type
        assert received.data == msg.data

    def test_send_receive_from_scheduler(self):
        bus = MessageBus()
        msg = Message(
            message_type=MessageType.FINISH_TASK,
            data={"result": "done"},
        )
        
        bus.send_from_scheduler(msg)
        received = bus.receive_from_scheduler(timeout=1.0)
        
        assert received is not None
        assert received.message_type == msg.message_type
        assert received.data == msg.data

    def test_receive_timeout_returns_none(self):
        bus = MessageBus()
        result = bus.receive_in_scheduler(timeout=0.01)
        assert result is None

    def test_receive_from_scheduler_timeout_returns_none(self):
        bus = MessageBus()
        result = bus.receive_from_scheduler(timeout=0.01)
        assert result is None

    def test_signal_and_wait_ready(self):
        bus = MessageBus()
        bus.signal_ready()
        
        result = bus.wait_ready(timeout=1.0)
        assert result is True

    def test_wait_ready_timeout(self):
        bus = MessageBus()
        result = bus.wait_ready(timeout=0.01)
        assert result is False

    def test_multiple_messages(self):
        bus = MessageBus()
        messages = [
            Message(MessageType.RUN_TASK, {"id": "1"}),
            Message(MessageType.RUN_TASK, {"id": "2"}),
            Message(MessageType.RUN_TASK, {"id": "3"}),
        ]

        for msg in messages:
            bus.send_to_scheduler(msg)

        received = []
        for _ in range(3):
            msg = bus.receive_in_scheduler(timeout=1.0)
            if msg:
                received.append(msg)

        assert len(received) == 3
        assert [m.data["id"] for m in received] == ["1", "2", "3"]


class TestMessageBusBackpressure:
    """Tests for MessageBus backpressure support."""

    def test_custom_capacity(self):
        """Test MessageBus with custom queue capacities."""
        bus = MessageBus(to_scheduler_capacity=100, from_scheduler_capacity=50)
        assert bus._to_scheduler_capacity == 100
        assert bus._from_scheduler_capacity == 50

    def test_queue_size_properties(self):
        """Test queue size monitoring properties."""
        bus = MessageBus(to_scheduler_capacity=100)

        # Initially empty
        assert bus.to_scheduler_size == 0
        assert bus.from_scheduler_size == 0

        # Add messages
        msg = Message(MessageType.RUN_TASK, {"id": "1"})
        bus.send_to_scheduler(msg)

        assert bus.to_scheduler_size == 1

    def test_is_full_methods(self):
        """Test queue full check methods."""
        bus = MessageBus(to_scheduler_capacity=2, from_scheduler_capacity=2)

        assert bus.is_to_scheduler_full() is False
        assert bus.is_from_scheduler_full() is False

        # Fill to_scheduler queue
        bus.send_to_scheduler(Message(MessageType.RUN_TASK, {"id": "1"}))
        bus.send_to_scheduler(Message(MessageType.RUN_TASK, {"id": "2"}))

        assert bus.is_to_scheduler_full() is True

    def test_send_to_full_queue_returns_false(self):
        """Test that sending to a full queue returns False."""
        bus = MessageBus(to_scheduler_capacity=1)

        # First message succeeds
        result1 = bus.send_to_scheduler(
            Message(MessageType.RUN_TASK, {"id": "1"}),
            block=False
        )
        assert result1 is True

        # Second message fails (queue full)
        result2 = bus.send_to_scheduler(
            Message(MessageType.RUN_TASK, {"id": "2"}),
            block=False
        )
        assert result2 is False

    def test_try_send_to_scheduler(self):
        """Test non-blocking send method."""
        bus = MessageBus(to_scheduler_capacity=1)

        # First succeeds
        assert bus.try_send_to_scheduler(Message(MessageType.RUN_TASK, {"id": "1"})) is True

        # Second fails (non-blocking)
        assert bus.try_send_to_scheduler(Message(MessageType.RUN_TASK, {"id": "2"})) is False

    def test_get_backpressure_status(self):
        """Test backpressure status monitoring."""
        bus = MessageBus(to_scheduler_capacity=100, from_scheduler_capacity=50)

        # Add some messages
        for i in range(10):
            bus.send_to_scheduler(Message(MessageType.RUN_TASK, {"id": str(i)}))

        status = bus.get_backpressure_status()

        assert status["to_scheduler_size"] == 10
        assert status["to_scheduler_capacity"] == 100
        assert status["to_scheduler_utilization"] == 0.1
        assert status["from_scheduler_size"] == 0
        assert status["from_scheduler_capacity"] == 50
        assert status["is_to_scheduler_full"] is False
        assert status["is_from_scheduler_full"] is False


class TestMessageTypeBackpressure:
    """Test TASK_REJECTED message type for backpressure."""

    def test_task_rejected_type_exists(self):
        """Verify TASK_REJECTED message type exists."""
        assert MessageType.TASK_REJECTED.value == "task_rejected"

    def test_task_rejected_message(self):
        """Test creating a TASK_REJECTED message."""
        msg = Message(
            message_type=MessageType.TASK_REJECTED,
            data={
                "task_id": "task-1",
                "workflow_id": "wf-1",
                "reason": "backpressure",
                "pending_count": 10000,
                "max_pending": 10000,
            }
        )

        assert msg.message_type == MessageType.TASK_REJECTED
        assert msg.data["reason"] == "backpressure"
