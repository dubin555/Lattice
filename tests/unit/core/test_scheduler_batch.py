"""
Unit tests for Scheduler batching integration.
"""
import pytest
import time
from unittest.mock import MagicMock, patch, PropertyMock
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

from lattice.core.scheduler.scheduler import Scheduler, _run_batch_task
from lattice.core.scheduler.message_bus import MessageBus, Message, MessageType
from lattice.config.batch import BatchConfig
from lattice.core.runtime.task import CodeTaskRuntime
from lattice.executor.base import ExecutorType
from lattice.config.defaults import BatchRule


@dataclass
class MockTaskHandle:
    handle_id: str


class MockExecutor:
    def __init__(self):
        self.submitted = []
        self.results = {}

    def initialize(self):
        pass

    def submit(self, submission):
        handle = MockTaskHandle(handle_id=f"handle_{len(self.submitted)}")
        self.submitted.append((submission, handle))
        return handle

    def wait(self, handles, timeout=0):
        # Return all handles as done
        return handles, []

    def get_result(self, handle):
        return self.results.get(handle.handle_id, None)

    def cancel(self, handle):
        pass

    def shutdown(self):
        pass


class TestSchedulerBatchIntegration:
    def test_scheduler_init_with_batch_rules(self):
        """Test that Scheduler accepts batch_rules parameter."""
        bus = MessageBus()
        rules = [
            BatchRule(pattern="embed_", match_type="prefix", batch_size=32),
        ]
        scheduler = Scheduler(
            message_bus=bus,
            executor_type=ExecutorType.LOCAL,
            batch_rules=rules,
        )
        assert scheduler._batch_collector is not None
        assert len(scheduler._batch_collector._rules) == 1

    def test_batchable_task_added_to_collector(self):
        """Test that batchable tasks are added to BatchCollector."""
        bus = MessageBus()
        scheduler = Scheduler(message_bus=bus, executor_type=ExecutorType.LOCAL)

        # Create a batchable task
        task = CodeTaskRuntime(
            workflow_id="wf1",
            task_id="task1",
            resources={"cpu": 1},
            task_name="embed_texts",
            batch_config={"enabled": True, "batch_size": 2, "batch_timeout": 0.0},
        )

        scheduler._pending_tasks.append(task)

        # Mock executor to avoid actual execution
        scheduler._executor = MockExecutor()

        # Dispatch should add task to batch collector, not submit immediately
        scheduler._dispatch_pending_tasks()

        assert scheduler._batch_collector.pending_count("embed_texts") == 1
        assert len(scheduler._executor.submitted) == 0

    def test_non_batchable_task_dispatched_immediately(self):
        """Test that non-batchable tasks are dispatched immediately."""
        bus = MessageBus()
        scheduler = Scheduler(message_bus=bus, executor_type=ExecutorType.LOCAL)

        # Create a non-batchable task
        task = CodeTaskRuntime(
            workflow_id="wf1",
            task_id="task1",
            resources={"cpu": 1},
            task_name="process_data",
            serialized_code="dGVzdA==",  # base64 encoded
        )

        scheduler._pending_tasks.append(task)
        scheduler._executor = MockExecutor()

        scheduler._dispatch_pending_tasks()

        assert scheduler._batch_collector.pending_count() == 0
        assert len(scheduler._executor.submitted) == 1

    def test_batch_dispatched_when_size_reached(self):
        """Test that batch is dispatched when batch_size is reached."""
        bus = MessageBus()
        scheduler = Scheduler(message_bus=bus, executor_type=ExecutorType.LOCAL)
        scheduler._executor = MockExecutor()

        # Add first task
        task1 = CodeTaskRuntime(
            workflow_id="wf1",
            task_id="task1",
            resources={"cpu": 1},
            task_name="embed_texts",
            batch_config={"enabled": True, "batch_size": 2, "batch_timeout": 0.0},
            serialized_code="dGVzdA==",
        )
        scheduler._pending_tasks.append(task1)
        scheduler._dispatch_pending_tasks()

        # Batch not ready yet
        scheduler._dispatch_batched_tasks()
        assert len(scheduler._executor.submitted) == 0

        # Add second task
        task2 = CodeTaskRuntime(
            workflow_id="wf1",
            task_id="task2",
            resources={"cpu": 1},
            task_name="embed_texts",
            batch_config={"enabled": True, "batch_size": 2, "batch_timeout": 0.0},
            serialized_code="dGVzdA==",
        )
        scheduler._pending_tasks.append(task2)
        scheduler._dispatch_pending_tasks()

        # Now batch should be ready
        scheduler._dispatch_batched_tasks()
        assert len(scheduler._executor.submitted) == 1
        assert "batch_embed_texts_task1" in scheduler._batch_tasks

    def test_batch_dispatched_on_timeout(self):
        """Test that batch is dispatched when timeout expires."""
        bus = MessageBus()
        scheduler = Scheduler(message_bus=bus, executor_type=ExecutorType.LOCAL)
        scheduler._executor = MockExecutor()

        task = CodeTaskRuntime(
            workflow_id="wf1",
            task_id="task1",
            resources={"cpu": 1},
            task_name="embed_texts",
            batch_config={"enabled": True, "batch_size": 100, "batch_timeout": 0.05},
            serialized_code="dGVzdA==",
        )
        scheduler._pending_tasks.append(task)
        scheduler._dispatch_pending_tasks()

        # Batch not ready yet
        scheduler._dispatch_batched_tasks()
        assert len(scheduler._executor.submitted) == 0

        # Wait for timeout
        time.sleep(0.06)

        # Now batch should be ready
        scheduler._dispatch_batched_tasks()
        assert len(scheduler._executor.submitted) == 1


class TestRunBatchTask:
    def test_run_batch_task_with_serialized_code(self):
        """Test _run_batch_task with serialized code."""
        import base64
        import cloudpickle

        def batch_func(inputs):
            return [inp["x"] * 2 for inp in inputs]

        serialized = base64.b64encode(cloudpickle.dumps(batch_func)).decode()
        inputs = [{"x": 1}, {"x": 2}, {"x": 3}]

        results = _run_batch_task(None, serialized, inputs)
        assert results == [2, 4, 6]

    def test_run_batch_task_with_code_string(self):
        """Test _run_batch_task with code string (falls back to individual execution)."""
        # CodeRunner is used for code string, which doesn't support batching
        # So it executes each input separately
        # This test just verifies the code path doesn't error
        pass  # Skip for now as it requires CodeRunner mocking


class TestBatchRuleIntegration:
    def test_prefix_rule_groups_tasks(self):
        """Test that prefix rules group tasks correctly."""
        rules = [
            BatchRule(
                pattern="embed_",
                match_type="prefix",
                batch_size=2,
                group_key="embedding_group",
            )
        ]
        bus = MessageBus()
        scheduler = Scheduler(
            message_bus=bus,
            executor_type=ExecutorType.LOCAL,
            batch_rules=rules,
        )
        scheduler._executor = MockExecutor()

        # Add tasks with different names but same prefix
        task1 = CodeTaskRuntime(
            workflow_id="wf1",
            task_id="task1",
            resources={"cpu": 1},
            task_name="embed_texts",
            batch_config={"enabled": True, "batch_size": 10},
            serialized_code="dGVzdA==",
        )
        task2 = CodeTaskRuntime(
            workflow_id="wf1",
            task_id="task2",
            resources={"cpu": 1},
            task_name="embed_images",
            batch_config={"enabled": True, "batch_size": 10},
            serialized_code="dGVzdA==",
        )

        scheduler._pending_tasks = [task1, task2]
        scheduler._dispatch_pending_tasks()

        # Both should be in the same group
        assert scheduler._batch_collector.pending_count("embedding_group") == 2

    def test_regex_rule_groups_tasks(self):
        """Test that regex rules group tasks correctly."""
        rules = [
            BatchRule(
                pattern=".*_embedding$",
                match_type="regex",
                batch_size=2,
            )
        ]
        bus = MessageBus()
        scheduler = Scheduler(
            message_bus=bus,
            executor_type=ExecutorType.LOCAL,
            batch_rules=rules,
        )
        scheduler._executor = MockExecutor()

        task1 = CodeTaskRuntime(
            workflow_id="wf1",
            task_id="task1",
            resources={"cpu": 1},
            task_name="text_embedding",
            batch_config={"enabled": True, "batch_size": 10},
            serialized_code="dGVzdA==",
        )
        task2 = CodeTaskRuntime(
            workflow_id="wf1",
            task_id="task2",
            resources={"cpu": 1},
            task_name="image_embedding",
            batch_config={"enabled": True, "batch_size": 10},
            serialized_code="dGVzdA==",
        )

        scheduler._pending_tasks = [task1, task2]
        scheduler._dispatch_pending_tasks()

        # Both should match the regex pattern
        assert scheduler._batch_collector.pending_count(".*_embedding$") == 2
