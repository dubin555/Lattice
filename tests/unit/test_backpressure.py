"""
Unit tests for backpressure functionality.

Tests cover:
- BackpressureError exception
- API exception handling for backpressure
- Scheduler pending task limits
"""
import asyncio
import pytest
from unittest.mock import MagicMock

from lattice.exceptions import BackpressureError, ServerError
from lattice.core.scheduler.message_bus import MessageBus, Message, MessageType


class TestBackpressureError:
    """Tests for BackpressureError exception."""

    def test_inherits_from_server_error(self):
        """BackpressureError should be a ServerError."""
        error = BackpressureError()
        assert isinstance(error, ServerError)

    def test_default_message(self):
        """Test default error message."""
        error = BackpressureError()
        assert "backpressure" in str(error).lower()

    def test_custom_message(self):
        """Test custom error message."""
        error = BackpressureError(message="Queue full")
        assert "Queue full" in str(error)

    def test_with_queue_details(self):
        """Test error with queue capacity details."""
        error = BackpressureError(
            message="Task rejected",
            queue_name="pending_tasks",
            current_size=10000,
            capacity=10000,
        )

        assert error.queue_name == "pending_tasks"
        assert error.current_size == 10000
        assert error.capacity == 10000
        assert error.details["utilization"] == 1.0

    def test_utilization_calculation(self):
        """Test utilization is calculated correctly."""
        error = BackpressureError(
            current_size=500,
            capacity=1000,
        )
        assert error.details["utilization"] == 0.5

    def test_zero_capacity_handling(self):
        """Test handling of zero capacity (edge case)."""
        error = BackpressureError(
            current_size=0,
            capacity=0,
        )
        assert error.details["utilization"] == 1.0


class TestSchedulerBackpressure:
    """Tests for Scheduler backpressure behavior."""

    def test_scheduler_max_pending_tasks_parameter(self):
        """Test that Scheduler accepts max_pending_tasks parameter."""
        from lattice.core.scheduler.scheduler import Scheduler, DEFAULT_MAX_PENDING_TASKS

        bus = MessageBus()

        # Default value
        scheduler = Scheduler(message_bus=bus)
        assert scheduler.max_pending_tasks == DEFAULT_MAX_PENDING_TASKS

        # Custom value
        scheduler2 = Scheduler(message_bus=bus, max_pending_tasks=100)
        assert scheduler2.max_pending_tasks == 100

    def test_scheduler_pending_task_count(self):
        """Test pending task count property."""
        from lattice.core.scheduler.scheduler import Scheduler

        bus = MessageBus()
        scheduler = Scheduler(message_bus=bus)

        # Initially zero
        assert scheduler.pending_task_count == 0

    def test_scheduler_is_at_capacity(self):
        """Test is_at_capacity method."""
        from lattice.core.scheduler.scheduler import Scheduler

        bus = MessageBus()
        scheduler = Scheduler(message_bus=bus, max_pending_tasks=0)

        # With max=0, should always be at capacity
        assert scheduler.is_at_capacity() is True

    def test_scheduler_get_backpressure_status(self):
        """Test get_backpressure_status method."""
        from lattice.core.scheduler.scheduler import Scheduler

        bus = MessageBus()
        scheduler = Scheduler(message_bus=bus, max_pending_tasks=1000)

        status = scheduler.get_backpressure_status()

        assert "pending_task_count" in status
        assert "max_pending_tasks" in status
        assert "pending_utilization" in status
        assert "is_at_capacity" in status
        assert "running_task_count" in status
        assert "batch_group_count" in status


class TestBatchCollectorGroupCount:
    """Test BatchCollector group_count method."""

    def test_group_count(self):
        """Test group_count returns correct count."""
        from lattice.core.scheduler.batch_collector import BatchCollector
        from lattice.config.batch import BatchConfig

        collector = BatchCollector()

        # Initially zero
        assert collector.group_count() == 0

        # Add task to create a group
        mock_task = MagicMock()
        collector.add_task("task_name", mock_task, BatchConfig(batch_size=10))

        assert collector.group_count() == 1


class TestAPIBackpressureHandling:
    """Tests for API layer backpressure handling."""

    def test_backpressure_error_returns_503(self):
        """Test that BackpressureError results in 503 response."""
        from fastapi import HTTPException
        from lattice.api.exceptions import handle_route_exceptions

        @handle_route_exceptions
        async def failing_route():
            raise BackpressureError(
                message="System overloaded",
                queue_name="pending_tasks",
                current_size=10000,
                capacity=10000,
            )

        with pytest.raises(HTTPException) as exc_info:
            asyncio.get_event_loop().run_until_complete(failing_route())

        assert exc_info.value.status_code == 503
        assert "Retry-After" in exc_info.value.headers
        assert exc_info.value.headers["Retry-After"] == "1"

    def test_backpressure_error_includes_details(self):
        """Test that BackpressureError response includes capacity details."""
        from fastapi import HTTPException
        from lattice.api.exceptions import handle_route_exceptions

        @handle_route_exceptions
        async def failing_route():
            raise BackpressureError(
                message="Queue full",
                queue_name="pending_tasks",
                current_size=5000,
                capacity=5000,
            )

        with pytest.raises(HTTPException) as exc_info:
            asyncio.get_event_loop().run_until_complete(failing_route())

        detail = exc_info.value.detail
        assert detail["queue_name"] == "pending_tasks"
        assert detail["current_size"] == 5000
        assert detail["capacity"] == 5000
        assert detail["retry_after"] == 1
