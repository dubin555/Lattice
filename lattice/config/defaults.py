"""
Centralized configuration defaults for Lattice.

This module provides a single source of truth for all default configurations
used across the Lattice framework.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from enum import Enum


class ExecutorType(str, Enum):
    """Executor backend types."""
    RAY = "ray"
    LOCAL = "local"


class SandboxLevel(str, Enum):
    """Sandbox isolation levels."""
    NONE = "none"
    SUBPROCESS = "subprocess"
    SECCOMP = "seccomp"
    DOCKER = "docker"


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
