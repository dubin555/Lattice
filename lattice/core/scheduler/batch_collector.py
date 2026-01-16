"""
Batch collector for task batching.

Collects tasks with the same function signature and triggers batch execution
when batch_size is reached or batch_timeout expires.

Supports three ways to configure batching:
1. Task-level: via @task(batch_size=32, batch_timeout=0.1)
2. Rule-based: via BatchRule with pattern matching (exact, prefix, regex)
3. Default: via BATCH_DEFAULTS global configuration
"""
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

from lattice.config.defaults import BATCH_DEFAULTS, BatchRule

logger = logging.getLogger(__name__)


@dataclass
class BatchConfig:
    """Configuration for a batch group."""
    batch_size: int = BATCH_DEFAULTS.default_batch_size
    batch_timeout: float = BATCH_DEFAULTS.default_batch_timeout

    def __post_init__(self):
        if self.batch_size > BATCH_DEFAULTS.max_batch_size:
            self.batch_size = BATCH_DEFAULTS.max_batch_size
        if self.batch_timeout > BATCH_DEFAULTS.max_batch_timeout:
            self.batch_timeout = BATCH_DEFAULTS.max_batch_timeout

    @classmethod
    def from_rule(cls, rule: BatchRule) -> "BatchConfig":
        """Create BatchConfig from a BatchRule."""
        return cls(
            batch_size=rule.batch_size,
            batch_timeout=rule.batch_timeout,
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BatchConfig":
        """Create BatchConfig from a dictionary."""
        return cls(
            batch_size=data.get("batch_size", BATCH_DEFAULTS.default_batch_size),
            batch_timeout=data.get("batch_timeout", BATCH_DEFAULTS.default_batch_timeout),
        )


@dataclass
class BatchGroup:
    """A group of tasks waiting to be batched together."""
    config: BatchConfig
    tasks: List[Any] = field(default_factory=list)
    first_task_time: Optional[float] = None

    def add_task(self, task: Any) -> None:
        if not self.tasks:
            self.first_task_time = time.time()
        self.tasks.append(task)

    def is_ready(self) -> bool:
        """Check if batch is ready to be dispatched."""
        if not self.tasks:
            return False
        if len(self.tasks) >= self.config.batch_size:
            return True
        if self.config.batch_timeout > 0 and self.first_task_time:
            elapsed = time.time() - self.first_task_time
            if elapsed >= self.config.batch_timeout:
                return True
        return False

    def clear(self) -> List[Any]:
        """Clear and return all tasks."""
        tasks = self.tasks
        self.tasks = []
        self.first_task_time = None
        return tasks


class BatchCollector:
    """
    Collects tasks for batching based on task function name or rules.

    Tasks can be grouped by:
    - Exact task name
    - BatchRule with prefix/regex matching

    A batch is dispatched when:
    - batch_size is reached, OR
    - batch_timeout expires (if configured)

    Thread-safe: can be used from the scheduler thread.
    """

    def __init__(self, rules: Optional[List[BatchRule]] = None):
        """
        Initialize BatchCollector.

        Args:
            rules: Optional list of BatchRules for pattern-based matching.
                   Rules are evaluated in order; first match wins.
        """
        self._groups: Dict[str, BatchGroup] = {}
        self._rules: List[BatchRule] = rules or []
        self._lock = threading.Lock()

    def add_rule(self, rule: BatchRule) -> None:
        """Add a batch rule for pattern matching."""
        with self._lock:
            self._rules.append(rule)

    def add_rules(self, rules: List[BatchRule]) -> None:
        """Add multiple batch rules."""
        with self._lock:
            self._rules.extend(rules)

    def _find_matching_rule(self, task_name: str) -> Optional[BatchRule]:
        """Find the first matching rule for a task name."""
        for rule in self._rules:
            if rule.matches(task_name):
                return rule
        return None

    def _get_group_key(self, task_name: str, rule: Optional[BatchRule]) -> str:
        """Get the group key for a task."""
        if rule:
            return rule.get_group_key()
        return task_name

    def register_batch_config(self, group_key: str, config: BatchConfig) -> None:
        """Register batch configuration for a task group."""
        with self._lock:
            if group_key not in self._groups:
                self._groups[group_key] = BatchGroup(config=config)

    def add_task(
        self,
        task_name: str,
        task: Any,
        config: Optional[BatchConfig] = None,
    ) -> str:
        """
        Add a task to its batch group.

        Args:
            task_name: The task function name.
            task: The task runtime object.
            config: Optional batch config from task-level settings.
                    If not provided, tries rule matching, then uses default.

        Returns:
            The group key the task was added to.
        """
        with self._lock:
            # Priority: task-level config > rule-based config > default
            rule = self._find_matching_rule(task_name)
            group_key = self._get_group_key(task_name, rule)

            if group_key not in self._groups:
                if config:
                    batch_config = config
                elif rule:
                    batch_config = BatchConfig.from_rule(rule)
                else:
                    batch_config = BatchConfig()
                self._groups[group_key] = BatchGroup(config=batch_config)

            self._groups[group_key].add_task(task)
            return group_key

    def get_ready_batches(self) -> Dict[str, List[Any]]:
        """
        Get all batches that are ready to be dispatched.

        Returns:
            Dict mapping group_key to list of tasks ready for batch execution.
        """
        ready = {}
        with self._lock:
            for group_key, group in self._groups.items():
                if group.is_ready():
                    ready[group_key] = group.clear()
        return ready

    def get_batch_for_group(self, group_key: str) -> Optional[List[Any]]:
        """
        Get batch for a specific group if ready.

        Args:
            group_key: The group key (task name or rule group key).

        Returns:
            List of tasks if batch is ready, None otherwise.
        """
        with self._lock:
            if group_key in self._groups and self._groups[group_key].is_ready():
                return self._groups[group_key].clear()
        return None

    def force_flush(self, group_key: Optional[str] = None) -> Dict[str, List[Any]]:
        """
        Force flush batches regardless of batch_size/timeout.

        Args:
            group_key: If specified, only flush that group's batch.
                       If None, flush all batches.

        Returns:
            Dict mapping group_key to list of flushed tasks.
        """
        flushed = {}
        with self._lock:
            if group_key:
                if group_key in self._groups and self._groups[group_key].tasks:
                    flushed[group_key] = self._groups[group_key].clear()
            else:
                for key, group in self._groups.items():
                    if group.tasks:
                        flushed[key] = group.clear()
        return flushed

    def pending_count(self, group_key: Optional[str] = None) -> int:
        """Get count of pending tasks in batches."""
        with self._lock:
            if group_key:
                group = self._groups.get(group_key)
                return len(group.tasks) if group else 0
            return sum(len(g.tasks) for g in self._groups.values())

    def clear(self) -> None:
        """Clear all batch groups."""
        with self._lock:
            self._groups.clear()

    def clear_rules(self) -> None:
        """Clear all batch rules."""
        with self._lock:
            self._rules.clear()
