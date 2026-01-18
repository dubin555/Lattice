"""
Base types and configuration for sandbox execution.

This module provides the core types and configuration classes used by all
sandbox implementations.
"""
import logging
from enum import Enum
from typing import Dict, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class SandboxLevel(str, Enum):
    """Sandbox isolation levels."""
    NONE = "none"
    SUBPROCESS = "subprocess"
    SECCOMP = "seccomp"
    DOCKER = "docker"


@dataclass
class SandboxConfig:
    level: SandboxLevel = SandboxLevel.SUBPROCESS
    timeout: int = 300
    max_memory_mb: int = 2048
    max_cpu_time: int = 300
    allowed_imports: Optional[list] = None
    docker_image: str = "python:3.11-slim"
    network_enabled: bool = False
    mount_paths: Dict[str, str] = field(default_factory=dict)
    allowed_syscalls: Optional[list] = None


class SandboxError(Exception):
    """Base exception for sandbox errors."""
    pass


class TimeoutError(SandboxError):
    """Raised when task execution times out."""
    pass


class ResourceLimitError(SandboxError):
    """Raised when resource limits are exceeded."""
    pass


# Global sandbox configuration
_global_sandbox_config: Optional[SandboxConfig] = None


def set_sandbox_config(config: SandboxConfig) -> None:
    """Set the global sandbox configuration."""
    global _global_sandbox_config
    _global_sandbox_config = config
    logger.info(f"Sandbox configured: level={config.level.value}, timeout={config.timeout}s")


def get_sandbox_config() -> SandboxConfig:
    """Get the global sandbox configuration, creating a default if none exists."""
    global _global_sandbox_config
    if _global_sandbox_config is None:
        _global_sandbox_config = SandboxConfig()
    return _global_sandbox_config
