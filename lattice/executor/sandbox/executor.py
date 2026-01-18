"""
Unified sandbox executor that delegates to the appropriate sandbox implementation.

This module provides a single entry point for sandbox execution, automatically
selecting the appropriate backend based on the configured isolation level.
"""
from typing import Dict, Any, Optional

from lattice.executor.sandbox.base import (
    SandboxConfig,
    SandboxLevel,
    get_sandbox_config,
)
from lattice.executor.sandbox.subprocess import SubprocessSandbox
from lattice.executor.sandbox.docker import DockerSandbox


class SandboxExecutor:
    """Unified executor that selects the appropriate sandbox based on config."""

    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or SandboxConfig()
        self._sandbox = self._create_sandbox()

    def _create_sandbox(self):
        """Create the appropriate sandbox instance based on config level."""
        if self.config.level == SandboxLevel.NONE:
            return None
        elif self.config.level in (SandboxLevel.SUBPROCESS, SandboxLevel.SECCOMP):
            return SubprocessSandbox(self.config)
        elif self.config.level == SandboxLevel.DOCKER:
            return DockerSandbox(self.config)
        raise ValueError(f"Unknown sandbox level: {self.config.level}")

    def execute(
        self,
        code_str: Optional[str] = None,
        serialized_code: Optional[str] = None,
        task_input_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute code using the configured sandbox level.

        Args:
            code_str: Python code string containing a function definition.
            serialized_code: Base64-encoded cloudpickle serialized function.
            task_input_data: Input data to pass to the function.

        Returns:
            The result returned by the executed function.
        """
        if self.config.level == SandboxLevel.NONE:
            return self._execute_direct(code_str, serialized_code, task_input_data)
        return self._sandbox.execute(code_str, serialized_code, task_input_data)

    def _execute_direct(
        self,
        code_str: Optional[str],
        serialized_code: Optional[str],
        task_input_data: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Execute task directly without sandbox isolation.

        Uses the unified code execution utilities from code_executor.
        """
        from lattice.executor.code_executor import execute_task
        return execute_task(code_str, serialized_code, task_input_data)


def get_sandbox_executor() -> SandboxExecutor:
    """Get a SandboxExecutor configured with the global sandbox config."""
    return SandboxExecutor(get_sandbox_config())
