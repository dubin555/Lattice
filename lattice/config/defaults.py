"""
Centralized configuration defaults for Lattice.

This module provides a single source of truth for all default configurations
used across the Lattice framework.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from enum import Enum

# Import enums from their canonical locations
from lattice.executor.base import ExecutorType
from lattice.executor.sandbox import SandboxLevel


@dataclass(frozen=True)
class ResourceDefaults:
    """Default resource allocation for tasks."""
    cpu: int = 1
    cpu_mem: int = 0  # 0 means no limit
    gpu: int = 0
    gpu_mem: int = 0
    
    def to_dict(self) -> Dict[str, int]:
        return {
            "cpu": self.cpu,
            "cpu_mem": self.cpu_mem,
            "gpu": self.gpu,
            "gpu_mem": self.gpu_mem,
        }


@dataclass(frozen=True)
class ServerDefaults:
    """Default server configuration."""
    host: str = "0.0.0.0"
    port: int = 8000
    ray_head_port: int = 6379
    log_level: str = "INFO"


@dataclass(frozen=True)
class SandboxDefaults:
    """Default sandbox configuration."""
    level: SandboxLevel = SandboxLevel.SUBPROCESS
    timeout: int = 300  # seconds
    max_memory_mb: int = 2048
    max_cpu_time: int = 300  # seconds
    max_processes: int = 50
    max_open_files: int = 256
    network_enabled: bool = False
    docker_image: str = "python:3.11-slim"


@dataclass(frozen=True)
class SchedulerDefaults:
    """Default scheduler configuration."""
    poll_interval: float = 0.1  # seconds
    max_retries: int = 0
    task_timeout: int = 3600  # seconds


@dataclass(frozen=True)
class BatchDefaults:
    """Default batching configuration for tasks.

    These defaults apply when a task enables batching but doesn't specify
    all batching parameters. Individual task configurations override these.
    """
    default_batch_size: int = 32
    default_batch_timeout: float = 0.1  # seconds
    max_batch_size: int = 256
    max_batch_timeout: float = 5.0  # seconds


@dataclass
class BatchRule:
    """A rule for matching tasks to batching configuration.

    Tasks can be matched by:
    - exact name match
    - prefix match (e.g., "embed_" matches "embed_texts", "embed_images")
    - regex pattern match (e.g., ".*_embedding$")
    """
    pattern: str
    match_type: str = "exact"  # "exact", "prefix", or "regex"
    batch_size: int = 32
    batch_timeout: float = 0.1  # seconds
    group_key: Optional[str] = None  # custom group key, defaults to pattern

    def matches(self, task_name: str) -> bool:
        """Check if this rule matches the given task name."""
        import re
        if self.match_type == "exact":
            return task_name == self.pattern
        elif self.match_type == "prefix":
            return task_name.startswith(self.pattern)
        elif self.match_type == "regex":
            return bool(re.match(self.pattern, task_name))
        return False

    def get_group_key(self) -> str:
        """Get the group key for batching tasks together."""
        return self.group_key or self.pattern


@dataclass(frozen=True)
class ClientDefaults:
    """Default client configuration."""
    timeout: int = 30  # seconds for HTTP requests
    retry_count: int = 3
    retry_delay: float = 1.0  # seconds


# Global default instances
RESOURCE_DEFAULTS = ResourceDefaults()
SERVER_DEFAULTS = ServerDefaults()
SANDBOX_DEFAULTS = SandboxDefaults()
SCHEDULER_DEFAULTS = SchedulerDefaults()
BATCH_DEFAULTS = BatchDefaults()
CLIENT_DEFAULTS = ClientDefaults()


def get_default_resources() -> Dict[str, int]:
    """Get default resource allocation as a dictionary."""
    return RESOURCE_DEFAULTS.to_dict()


def get_default_server_config() -> Dict[str, Any]:
    """Get default server configuration as a dictionary."""
    return {
        "host": SERVER_DEFAULTS.host,
        "port": SERVER_DEFAULTS.port,
        "ray_head_port": SERVER_DEFAULTS.ray_head_port,
        "log_level": SERVER_DEFAULTS.log_level,
    }
