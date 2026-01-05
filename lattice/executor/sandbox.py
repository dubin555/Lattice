"""
Sandbox execution environment for secure task execution.

Provides multiple isolation levels:
- NONE: Direct execution (fastest, no isolation)
- SUBPROCESS: Run in separate process with resource limits
- DOCKER: Run in Docker container (strongest isolation)
"""
import os
import sys
import json
import time
import signal
import base64
import tempfile
import subprocess
import logging
from enum import Enum
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class SandboxLevel(Enum):
    """Sandbox isolation levels."""
    NONE = "none"           # Direct execution, no isolation
    SUBPROCESS = "subprocess"  # Separate process with resource limits
    SECCOMP = "seccomp"     # Subprocess + seccomp syscall filtering (Linux only)
    DOCKER = "docker"       # Docker container isolation


@dataclass
class SandboxConfig:
    """Configuration for sandbox execution."""
    level: SandboxLevel = SandboxLevel.SUBPROCESS
    timeout: int = 300  # 5 minutes default
    max_memory_mb: int = 2048  # 2GB default
    max_cpu_time: int = 300  # CPU time limit in seconds
    allowed_imports: Optional[list] = None  # None = allow all
    docker_image: str = "python:3.11-slim"
    network_enabled: bool = False  # Disable network by default in Docker
    mount_paths: Dict[str, str] = field(default_factory=dict)
    allowed_syscalls: Optional[list] = None  # For seccomp: None = use default whitelist


class SandboxError(Exception):
    """Exception raised when sandbox execution fails."""
    pass


class TimeoutError(SandboxError):
    """Exception raised when task execution times out."""
    pass


class ResourceLimitError(SandboxError):
    """Exception raised when resource limits are exceeded."""
    pass


# Template for subprocess execution
SUBPROCESS_RUNNER_TEMPLATE = '''
import sys
import json
import base64
import resource
import signal

def set_resource_limits(max_memory_mb, max_cpu_time):
    """Set resource limits for the subprocess."""
    # Memory limit (in bytes)
    memory_bytes = max_memory_mb * 1024 * 1024
    try:
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
    except (ValueError, resource.error):
        pass  # May fail on some systems
    
    # CPU time limit
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (max_cpu_time, max_cpu_time))
    except (ValueError, resource.error):
        pass

def timeout_handler(signum, frame):
    raise TimeoutError("Task execution timed out")

def main():
    # Read input from stdin
    input_data = json.loads(sys.stdin.read())
    
    serialized_code = input_data.get("serialized_code")
    code_str = input_data.get("code_str")
    task_input_data = input_data.get("task_input_data", {})
    max_memory_mb = input_data.get("max_memory_mb", 2048)
    max_cpu_time = input_data.get("max_cpu_time", 300)
    timeout = input_data.get("timeout", 300)
    
    # Set resource limits
    set_resource_limits(max_memory_mb, max_cpu_time)
    
    # Set timeout
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout)
    
    try:
        if serialized_code:
            import cloudpickle
            func = cloudpickle.loads(base64.b64decode(serialized_code))
            result = func(task_input_data)
        elif code_str:
            # Execute code string
            import ast
            tree = ast.parse(code_str)
            
            # Extract function
            func_node = None
            import_nodes = []
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    func_node = node
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    import_nodes.append(node)
            
            if func_node is None:
                raise ValueError("No function definition found")
            
            namespace = {}
            
            # Execute imports
            for imp in import_nodes:
                module = ast.Module(body=[imp], type_ignores=[])
                code = compile(module, '<string>', 'exec')
                exec(code, namespace)
            
            # Execute function definition
            module = ast.Module(body=[func_node], type_ignores=[])
            code = compile(module, '<string>', 'exec')
            exec(code, namespace)
            
            result = namespace[func_node.name](task_input_data)
        else:
            raise ValueError("No code provided")
        
        # Cancel timeout
        signal.alarm(0)
        
        # Output result as JSON
        print(json.dumps({"success": True, "result": result}))
        
    except Exception as e:
        signal.alarm(0)
        print(json.dumps({"success": False, "error": str(e), "error_type": type(e).__name__}))
        sys.exit(1)

if __name__ == "__main__":
    main()
'''


class SubprocessSandbox:
    """Execute code in an isolated subprocess with resource limits."""
    
    def __init__(self, config: SandboxConfig):
        self.config = config
    
    def execute(
        self,
        code_str: Optional[str] = None,
        serialized_code: Optional[str] = None,
        task_input_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute code in subprocess sandbox."""
        
        # Prepare input data
        input_data = {
            "code_str": code_str,
            "serialized_code": serialized_code,
            "task_input_data": task_input_data or {},
            "max_memory_mb": self.config.max_memory_mb,
            "max_cpu_time": self.config.max_cpu_time,
            "timeout": self.config.timeout,
        }
        
        # Write runner script to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(SUBPROCESS_RUNNER_TEMPLATE)
            runner_path = f.name
        
        try:
            # Start subprocess
            process = subprocess.Popen(
                [sys.executable, runner_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                # Start in new process group for clean termination
                preexec_fn=os.setsid if hasattr(os, 'setsid') else None,
            )
            
            # Send input and wait for result
            try:
                stdout, stderr = process.communicate(
                    input=json.dumps(input_data),
                    timeout=self.config.timeout + 5  # Extra time for overhead
                )
            except subprocess.TimeoutExpired:
                # Kill the entire process group
                if hasattr(os, 'killpg'):
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                else:
                    process.kill()
                process.wait()
                raise TimeoutError(f"Task execution timed out after {self.config.timeout}s")
            
            if process.returncode != 0:
                # Try to parse error from stdout
                try:
                    result = json.loads(stdout)
                    if not result.get("success"):
                        raise SandboxError(f"{result.get('error_type', 'Error')}: {result.get('error')}")
                except json.JSONDecodeError:
                    raise SandboxError(f"Subprocess failed: {stderr or stdout}")
            
            # Parse result
            result = json.loads(stdout)
            if result.get("success"):
                return result.get("result")
            else:
                raise SandboxError(f"{result.get('error_type', 'Error')}: {result.get('error')}")
                
        finally:
            # Clean up temp file
            try:
                os.unlink(runner_path)
            except OSError:
                pass


SECCOMP_RUNNER_TEMPLATE = '''
import sys
import json
import base64
import resource
import signal
import ctypes
import struct

SECCOMP_MODE_FILTER = 2
PR_SET_SECCOMP = 22
PR_SET_NO_NEW_PRIVS = 38

AUDIT_ARCH_X86_64 = 0xc000003e
AUDIT_ARCH_AARCH64 = 0xc00000b7

SECCOMP_RET_KILL_PROCESS = 0x80000000
SECCOMP_RET_ALLOW = 0x7fff0000
SECCOMP_RET_ERRNO = 0x00050000

BPF_LD = 0x00
BPF_W = 0x00
BPF_ABS = 0x20
BPF_JMP = 0x05
BPF_JEQ = 0x10
BPF_K = 0x00
BPF_RET = 0x06

def bpf_stmt(code, k):
    return struct.pack("HBBI", code, 0, 0, k)

def bpf_jump(code, k, jt, jf):
    return struct.pack("HBBI", code, jt, jf, k)

SYSCALL_WHITELIST_X86_64 = [
    0, 1, 2, 3, 5, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 20, 21, 22, 24, 25,
    28, 32, 33, 39, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55,
    56, 57, 58, 59, 60, 61, 63, 72, 79, 80, 89, 97, 99, 102, 104, 105, 107,
    108, 110, 111, 115, 131, 137, 140, 158, 186, 202, 204, 217, 218, 228, 229,
    230, 231, 232, 233, 234, 257, 262, 273, 281, 284, 285, 290, 291, 292, 293,
    302, 318, 334,
]

SYSCALL_WHITELIST_ARM64 = [
    29, 35, 46, 48, 56, 57, 61, 62, 63, 64, 65, 66, 68, 78, 79, 80, 93, 94, 96,
    98, 99, 100, 101, 113, 124, 129, 131, 134, 135, 137, 153, 160, 169, 172,
    173, 174, 175, 176, 178, 179, 198, 200, 201, 203, 204, 210, 214, 215, 220,
    221, 222, 226, 227, 228, 233, 260, 261, 262, 263, 278, 279, 280, 281, 282,
    283, 284, 285, 291,
]

def apply_seccomp_filter(allowed_syscalls=None):
    import platform
    arch = platform.machine()
    
    if arch == "x86_64":
        audit_arch = AUDIT_ARCH_X86_64
        syscalls = allowed_syscalls or SYSCALL_WHITELIST_X86_64
    elif arch in ("aarch64", "arm64"):
        audit_arch = AUDIT_ARCH_AARCH64
        syscalls = allowed_syscalls or SYSCALL_WHITELIST_ARM64
    else:
        return False
    
    bpf_filter = b""
    bpf_filter += bpf_stmt(BPF_LD | BPF_W | BPF_ABS, 4)
    bpf_filter += bpf_jump(BPF_JMP | BPF_JEQ | BPF_K, audit_arch, 1, 0)
    bpf_filter += bpf_stmt(BPF_RET | BPF_K, SECCOMP_RET_KILL_PROCESS)
    bpf_filter += bpf_stmt(BPF_LD | BPF_W | BPF_ABS, 0)
    
    for syscall in syscalls:
        bpf_filter += bpf_jump(BPF_JMP | BPF_JEQ | BPF_K, syscall, 0, 1)
        bpf_filter += bpf_stmt(BPF_RET | BPF_K, SECCOMP_RET_ALLOW)
    
    bpf_filter += bpf_stmt(BPF_RET | BPF_K, SECCOMP_RET_KILL_PROCESS)
    
    class sock_filter(ctypes.Structure):
        _fields_ = [("code", ctypes.c_ushort), ("jt", ctypes.c_ubyte),
                    ("jf", ctypes.c_ubyte), ("k", ctypes.c_uint)]
    
    class sock_fprog(ctypes.Structure):
        _fields_ = [("len", ctypes.c_ushort), ("filter", ctypes.POINTER(sock_filter))]
    
    n_insns = len(bpf_filter) // 8
    filter_array = (sock_filter * n_insns)()
    for i in range(n_insns):
        insn = bpf_filter[i*8:(i+1)*8]
        code, jt, jf, k = struct.unpack("HBBI", insn)
        filter_array[i] = sock_filter(code, jt, jf, k)
    
    prog = sock_fprog(n_insns, filter_array)
    
    libc = ctypes.CDLL(None, use_errno=True)
    prctl = libc.prctl
    prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
    prctl.restype = ctypes.c_int
    
    if prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
        return False
    
    if prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, ctypes.addressof(prog), 0, 0) != 0:
        return False
    
    return True

def set_resource_limits(max_memory_mb, max_cpu_time):
    memory_bytes = max_memory_mb * 1024 * 1024
    try:
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
    except (ValueError, resource.error):
        pass
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (max_cpu_time, max_cpu_time))
    except (ValueError, resource.error):
        pass
    try:
        resource.setrlimit(resource.RLIMIT_NPROC, (50, 50))
    except (ValueError, resource.error):
        pass
    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
    except (ValueError, resource.error):
        pass

def timeout_handler(signum, frame):
    raise TimeoutError("Task execution timed out")

def main():
    input_data = json.loads(sys.stdin.read())
    
    serialized_code = input_data.get("serialized_code")
    code_str = input_data.get("code_str")
    task_input_data = input_data.get("task_input_data", {})
    max_memory_mb = input_data.get("max_memory_mb", 2048)
    max_cpu_time = input_data.get("max_cpu_time", 300)
    timeout = input_data.get("timeout", 300)
    enable_seccomp = input_data.get("enable_seccomp", True)
    allowed_syscalls = input_data.get("allowed_syscalls")
    
    set_resource_limits(max_memory_mb, max_cpu_time)
    
    if enable_seccomp:
        try:
            apply_seccomp_filter(allowed_syscalls)
        except Exception:
            pass
    
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout)
    
    try:
        if serialized_code:
            import cloudpickle
            func = cloudpickle.loads(base64.b64decode(serialized_code))
            result = func(task_input_data)
        elif code_str:
            import ast
            tree = ast.parse(code_str)
            
            func_node = None
            import_nodes = []
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    func_node = node
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    import_nodes.append(node)
            
            if func_node is None:
                raise ValueError("No function definition found")
            
            namespace = {}
            
            for imp in import_nodes:
                module = ast.Module(body=[imp], type_ignores=[])
                code = compile(module, '<string>', 'exec')
                exec(code, namespace)
            
            module = ast.Module(body=[func_node], type_ignores=[])
            code = compile(module, '<string>', 'exec')
            exec(code, namespace)
            
            result = namespace[func_node.name](task_input_data)
        else:
            raise ValueError("No code provided")
        
        signal.alarm(0)
        print(json.dumps({"success": True, "result": result}))
        
    except Exception as e:
        signal.alarm(0)
        print(json.dumps({"success": False, "error": str(e), "error_type": type(e).__name__}))
        sys.exit(1)

if __name__ == "__main__":
    main()
'''


class SeccompSandbox:
    """Execute code in subprocess with seccomp syscall filtering (Linux only)."""
    
    def __init__(self, config: SandboxConfig):
        self.config = config
        self._check_platform()
    
    def _check_platform(self):
        import platform
        if platform.system() != "Linux":
            logger.warning("Seccomp is only available on Linux. Falling back to subprocess sandbox.")
    
    def execute(
        self,
        code_str: Optional[str] = None,
        serialized_code: Optional[str] = None,
        task_input_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        import platform
        
        input_data = {
            "code_str": code_str,
            "serialized_code": serialized_code,
            "task_input_data": task_input_data or {},
            "max_memory_mb": self.config.max_memory_mb,
            "max_cpu_time": self.config.max_cpu_time,
            "timeout": self.config.timeout,
            "enable_seccomp": platform.system() == "Linux",
            "allowed_syscalls": self.config.allowed_syscalls,
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(SECCOMP_RUNNER_TEMPLATE)
            runner_path = f.name
        
        try:
            process = subprocess.Popen(
                [sys.executable, runner_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                preexec_fn=os.setsid if hasattr(os, 'setsid') else None,
            )
            
            try:
                stdout, stderr = process.communicate(
                    input=json.dumps(input_data),
                    timeout=self.config.timeout + 5
                )
            except subprocess.TimeoutExpired:
                if hasattr(os, 'killpg'):
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                else:
                    process.kill()
                process.wait()
                raise TimeoutError(f"Task execution timed out after {self.config.timeout}s")
            
            if process.returncode != 0:
                try:
                    result = json.loads(stdout)
                    if not result.get("success"):
                        raise SandboxError(f"{result.get('error_type', 'Error')}: {result.get('error')}")
                except json.JSONDecodeError:
                    raise SandboxError(f"Subprocess failed: {stderr or stdout}")
            
            result = json.loads(stdout)
            if result.get("success"):
                return result.get("result")
            else:
                raise SandboxError(f"{result.get('error_type', 'Error')}: {result.get('error')}")
                
        finally:
            try:
                os.unlink(runner_path)
            except OSError:
                pass


# Docker runner script template
DOCKER_RUNNER_SCRIPT = '''
import sys
import json
import base64

input_data = json.loads(sys.stdin.read())
serialized_code = input_data.get("serialized_code")
code_str = input_data.get("code_str")
task_input_data = input_data.get("task_input_data", {})

try:
    if serialized_code:
        import cloudpickle
        func = cloudpickle.loads(base64.b64decode(serialized_code))
        result = func(task_input_data)
    elif code_str:
        import ast
        tree = ast.parse(code_str)
        func_node = None
        import_nodes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_node = node
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                import_nodes.append(node)
        if func_node is None:
            raise ValueError("No function definition found")
        namespace = {}
        for imp in import_nodes:
            module = ast.Module(body=[imp], type_ignores=[])
            exec(compile(module, '<string>', 'exec'), namespace)
        module = ast.Module(body=[func_node], type_ignores=[])
        exec(compile(module, '<string>', 'exec'), namespace)
        result = namespace[func_node.name](task_input_data)
    else:
        raise ValueError("No code provided")
    print(json.dumps({"success": True, "result": result}))
except Exception as e:
    print(json.dumps({"success": False, "error": str(e), "error_type": type(e).__name__}))
    sys.exit(1)
'''


class DockerSandbox:
    """Execute code in an isolated Docker container."""
    
    def __init__(self, config: SandboxConfig):
        self.config = config
        self._check_docker()
    
    def _check_docker(self):
        """Check if Docker is available."""
        try:
            subprocess.run(
                ["docker", "version"],
                capture_output=True,
                check=True,
                timeout=10
            )
        except (subprocess.SubprocessError, FileNotFoundError):
            raise SandboxError("Docker is not available. Install Docker or use SUBPROCESS sandbox level.")
    
    def execute(
        self,
        code_str: Optional[str] = None,
        serialized_code: Optional[str] = None,
        task_input_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute code in Docker container."""
        
        input_data = {
            "code_str": code_str,
            "serialized_code": serialized_code,
            "task_input_data": task_input_data or {},
        }
        
        # Write runner script
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(DOCKER_RUNNER_SCRIPT)
            runner_path = f.name
        
        # Write input data
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(input_data, f)
            input_path = f.name
        
        try:
            # Build Docker command
            docker_cmd = [
                "docker", "run",
                "--rm",  # Remove container after execution
                "-i",    # Interactive (for stdin)
                f"--memory={self.config.max_memory_mb}m",
                f"--cpus=1",
                "--pids-limit=100",  # Limit number of processes
                "--read-only",       # Read-only filesystem
                "--tmpfs=/tmp:size=100m",  # Writable tmp
            ]
            
            # Network isolation
            if not self.config.network_enabled:
                docker_cmd.append("--network=none")
            
            # Security options
            docker_cmd.extend([
                "--security-opt=no-new-privileges",
                "--cap-drop=ALL",  # Drop all capabilities
            ])
            
            # Mount runner script
            docker_cmd.extend([
                "-v", f"{runner_path}:/app/runner.py:ro",
            ])
            
            # Additional mounts
            for host_path, container_path in self.config.mount_paths.items():
                docker_cmd.extend(["-v", f"{host_path}:{container_path}:ro"])
            
            # Image and command
            docker_cmd.extend([
                self.config.docker_image,
                "python", "/app/runner.py"
            ])
            
            # Run Docker container
            with open(input_path, 'r') as input_file:
                process = subprocess.Popen(
                    docker_cmd,
                    stdin=input_file,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
            
            try:
                stdout, stderr = process.communicate(timeout=self.config.timeout + 30)
            except subprocess.TimeoutExpired:
                process.kill()
                # Also try to stop any running container
                subprocess.run(["docker", "kill", "--signal=KILL"], capture_output=True)
                raise TimeoutError(f"Docker execution timed out after {self.config.timeout}s")
            
            if process.returncode != 0:
                try:
                    result = json.loads(stdout)
                    if not result.get("success"):
                        raise SandboxError(f"{result.get('error_type', 'Error')}: {result.get('error')}")
                except json.JSONDecodeError:
                    raise SandboxError(f"Docker execution failed: {stderr or stdout}")
            
            result = json.loads(stdout)
            if result.get("success"):
                return result.get("result")
            else:
                raise SandboxError(f"{result.get('error_type', 'Error')}: {result.get('error')}")
                
        finally:
            try:
                os.unlink(runner_path)
                os.unlink(input_path)
            except OSError:
                pass


class SandboxExecutor:
    """
    Unified sandbox executor that supports multiple isolation levels.
    
    Usage:
        executor = SandboxExecutor(SandboxConfig(level=SandboxLevel.SUBPROCESS))
        result = executor.execute(code_str="def task(params): return {'x': 1}", task_input_data={})
    """
    
    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or SandboxConfig()
        self._sandbox = self._create_sandbox()
    
    def _create_sandbox(self):
        """Create the appropriate sandbox based on config."""
        if self.config.level == SandboxLevel.NONE:
            return None
        elif self.config.level == SandboxLevel.SUBPROCESS:
            return SubprocessSandbox(self.config)
        elif self.config.level == SandboxLevel.SECCOMP:
            return SeccompSandbox(self.config)
        elif self.config.level == SandboxLevel.DOCKER:
            return DockerSandbox(self.config)
        else:
            raise ValueError(f"Unknown sandbox level: {self.config.level}")
    
    def execute(
        self,
        code_str: Optional[str] = None,
        serialized_code: Optional[str] = None,
        task_input_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute code in sandbox.
        
        Args:
            code_str: Python code string containing a function
            serialized_code: Base64-encoded cloudpickle serialized function
            task_input_data: Input parameters to pass to the function
            
        Returns:
            The return value of the executed function
            
        Raises:
            SandboxError: If execution fails
            TimeoutError: If execution times out
        """
        if self.config.level == SandboxLevel.NONE:
            # Direct execution (no sandbox)
            return self._execute_direct(code_str, serialized_code, task_input_data)
        else:
            return self._sandbox.execute(code_str, serialized_code, task_input_data)
    
    def _execute_direct(
        self,
        code_str: Optional[str],
        serialized_code: Optional[str],
        task_input_data: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Direct execution without sandbox (original behavior)."""
        import cloudpickle
        import ast
        
        task_input_data = task_input_data or {}
        
        if serialized_code:
            func = cloudpickle.loads(base64.b64decode(serialized_code))
            return func(task_input_data)
        elif code_str:
            tree = ast.parse(code_str)
            func_node = None
            import_nodes = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    func_node = node
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    import_nodes.append(node)
            
            if func_node is None:
                raise ValueError("No function definition found")
            
            namespace = {}
            for imp in import_nodes:
                module = ast.Module(body=[imp], type_ignores=[])
                exec(compile(module, '<string>', 'exec'), namespace)
            
            module = ast.Module(body=[func_node], type_ignores=[])
            exec(compile(module, '<string>', 'exec'), namespace)
            
            return namespace[func_node.name](task_input_data)
        else:
            raise ValueError("No code provided")


# Global sandbox configuration
_global_sandbox_config: Optional[SandboxConfig] = None


def set_sandbox_config(config: SandboxConfig):
    """Set global sandbox configuration."""
    global _global_sandbox_config
    _global_sandbox_config = config
    logger.info(f"Sandbox configured: level={config.level.value}, timeout={config.timeout}s")


def get_sandbox_config() -> SandboxConfig:
    """Get global sandbox configuration."""
    global _global_sandbox_config
    if _global_sandbox_config is None:
        _global_sandbox_config = SandboxConfig()
    return _global_sandbox_config


def get_sandbox_executor() -> SandboxExecutor:
    """Get a sandbox executor with the global configuration."""
    return SandboxExecutor(get_sandbox_config())
