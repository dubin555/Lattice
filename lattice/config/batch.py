"""
Unified BatchConfig for task batching configuration.

This module provides a single BatchConfig class that supports both:
1. Client-side task decoration (enabled flag, to_dict serialization)
2. Server-side batch collection (from_rule, from_dict, max limits)

The BatchConfig is used throughout the Lattice framework to configure
how tasks are batched together for efficient execution.
"""
from dataclasses import dataclass
from typing import Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from lattice.config.defaults import BatchRule

# Import BATCH_DEFAULTS lazily to avoid circular imports
_batch_defaults = None


def _get_batch_defaults():
    """Lazy import of BATCH_DEFAULTS to avoid circular imports."""
    global _batch_defaults
    if _batch_defaults is None:
        from lattice.config.defaults import BATCH_DEFAULTS
        _batch_defaults = BATCH_DEFAULTS
    return _batch_defaults


@dataclass
class BatchConfig:
    """Configuration for task batching.

    This class unifies batch configuration across the Lattice framework:
    - Client-side: Used by @task decorator to specify batching parameters
    - Server-side: Used by BatchCollector to manage batch groups

    Attributes:
        enabled: Whether batching is enabled for this task.
        batch_size: Maximum number of tasks to batch together.
        batch_timeout: Maximum wait time in seconds before triggering a batch.
            0 means no timeout (only trigger on batch_size).

    Example:
        # Client-side usage with @task decorator
        @task(inputs=["x"], outputs=["y"], batch_size=32, batch_timeout=0.1)
        def embed_text(data):
            ...

        # Server-side usage for batch collection
        config = BatchConfig.from_dict(task.batch_config)
        collector.add_task(task_name, task, config)
    """
    enabled: bool = False
    batch_size: int = 1
    batch_timeout: float = 0.0  # seconds, 0 means no timeout

    def __post_init__(self):
        """Apply maximum limits from BATCH_DEFAULTS if values exceed them."""
        defaults = _get_batch_defaults()
        if self.batch_size > defaults.max_batch_size:
            self.batch_size = defaults.max_batch_size
        if self.batch_timeout > defaults.max_batch_timeout:
            self.batch_timeout = defaults.max_batch_timeout

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for transmission over API.

        Returns:
            Dictionary with enabled, batch_size, and batch_timeout keys.
        """
        return {
            "enabled": self.enabled,
            "batch_size": self.batch_size,
            "batch_timeout": self.batch_timeout,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BatchConfig":
        """Create BatchConfig from a dictionary.

        Supports both client-side format (with 'enabled' field) and
        server-side format (without 'enabled', using BATCH_DEFAULTS).

        Args:
            data: Dictionary with batch configuration values.

        Returns:
            A new BatchConfig instance.
        """
        defaults = _get_batch_defaults()

        # Check if this is client-side format (has 'enabled' field)
        if "enabled" in data:
            return cls(
                enabled=data.get("enabled", False),
                batch_size=data.get("batch_size", 1),
                batch_timeout=data.get("batch_timeout", 0.0),
            )

        # Server-side format: If batch_size or batch_timeout is specified,
        # assume batching is enabled and use BATCH_DEFAULTS for missing values
        has_batch_config = "batch_size" in data or "batch_timeout" in data
        if has_batch_config:
            return cls(
                enabled=True,
                batch_size=data.get("batch_size", defaults.default_batch_size),
                batch_timeout=data.get("batch_timeout", defaults.default_batch_timeout),
            )

        # Empty dict with no batch config: return disabled defaults
        return cls()

    @classmethod
    def from_rule(cls, rule: "BatchRule") -> "BatchConfig":
        """Create BatchConfig from a BatchRule.

        Args:
            rule: A BatchRule instance with pattern matching configuration.

        Returns:
            A new BatchConfig instance with values from the rule.
        """
        return cls(
            enabled=True,
            batch_size=rule.batch_size,
            batch_timeout=rule.batch_timeout,
        )

    @classmethod
    def with_defaults(cls) -> "BatchConfig":
        """Create BatchConfig with BATCH_DEFAULTS values.

        Returns:
            A new BatchConfig with enabled=True and default batch settings.
        """
        defaults = _get_batch_defaults()
        return cls(
            enabled=True,
            batch_size=defaults.default_batch_size,
            batch_timeout=defaults.default_batch_timeout,
        )
