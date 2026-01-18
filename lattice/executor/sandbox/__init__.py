"""
Sandbox execution environment for secure task execution.

Provides multiple isolation levels:
- NONE: Direct execution (fastest, no isolation)
- SUBPROCESS: Run in separate process with resource limits
- SECCOMP: Subprocess with seccomp syscall filtering (Linux only)
- DOCKER: Run in Docker container (strongest isolation)

Note: The embedded runner scripts in subprocess.py and docker.py contain
execute_code logic that is derived from the utilities in code_executor.py.
These scripts must remain self-contained since they run in isolated environments
(subprocesses or Docker containers) without access to the main Lattice codebase.
Any changes to the core execution logic in code_executor.py should be reflected
in these embedded scripts to maintain consistency.
"""

# Core types and configuration
from lattice.executor.sandbox.base import (
    SandboxLevel,
    SandboxConfig,
    SandboxError,
    TimeoutError,
    ResourceLimitError,
    set_sandbox_config,
    get_sandbox_config,
)

# Sandbox implementations
from lattice.executor.sandbox.subprocess import SubprocessSandbox
from lattice.executor.sandbox.docker import DockerSandbox

# Unified executor
from lattice.executor.sandbox.executor import (
    SandboxExecutor,
    get_sandbox_executor,
)

__all__ = [
    # Core types
    "SandboxLevel",
    "SandboxConfig",
    "SandboxError",
    "TimeoutError",
    "ResourceLimitError",
    # Config functions
    "set_sandbox_config",
    "get_sandbox_config",
    # Sandbox implementations
    "SubprocessSandbox",
    "DockerSandbox",
    # Unified executor
    "SandboxExecutor",
    "get_sandbox_executor",
]
