"""
Subprocess-based sandbox execution.

Provides isolated task execution in a separate process with optional
seccomp filtering for additional security on Linux systems.

Note: The embedded runner scripts (RUNNER_TEMPLATE) contain execute_code logic
that is derived from the utilities in code_executor.py. These scripts must
remain self-contained since they run in isolated environments (subprocesses)
without access to the main Lattice codebase.
"""
import os
import sys
import json
import signal
import tempfile
import subprocess
from typing import Dict, Any, Optional

from lattice.executor.sandbox.base import (
    SandboxConfig,
    SandboxLevel,
    SandboxError,
    TimeoutError,
)


# RUNNER_TEMPLATE: Self-contained Python script for subprocess execution.
# The execute_code function below is derived from lattice.executor.code_executor
# but must be embedded here since subprocesses don't have access to the Lattice package.
RUNNER_TEMPLATE = '''
import sys
import json
import base64
import resource
import signal
{extra_imports}

{extra_code}

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
{extra_limits}

def timeout_handler(signum, frame):
    raise TimeoutError("Task execution timed out")

def execute_code(serialized_code, code_str, task_input_data):
    if serialized_code:
        import cloudpickle
        func = cloudpickle.loads(base64.b64decode(serialized_code))
        return func(task_input_data)
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
        namespace = {{}}
        for imp in import_nodes:
            module = ast.Module(body=[imp], type_ignores=[])
            exec(compile(module, '<string>', 'exec'), namespace)
        module = ast.Module(body=[func_node], type_ignores=[])
        exec(compile(module, '<string>', 'exec'), namespace)
        return namespace[func_node.name](task_input_data)
    else:
        raise ValueError("No code provided")

def main():
    input_data = json.loads(sys.stdin.read())
    serialized_code = input_data.get("serialized_code")
    code_str = input_data.get("code_str")
    task_input_data = input_data.get("task_input_data", {{}})
    max_memory_mb = input_data.get("max_memory_mb", 2048)
    max_cpu_time = input_data.get("max_cpu_time", 300)
    timeout = input_data.get("timeout", 300)

    set_resource_limits(max_memory_mb, max_cpu_time)
    {pre_execute}
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout)

    try:
        result = execute_code(serialized_code, code_str, task_input_data)
        signal.alarm(0)
        print(json.dumps({{"success": True, "result": result}}))
    except Exception as e:
        signal.alarm(0)
        print(json.dumps({{"success": False, "error": str(e), "error_type": type(e).__name__}}))
        sys.exit(1)

if __name__ == "__main__":
    main()
'''

# Seccomp-specific code that gets injected into RUNNER_TEMPLATE
SECCOMP_EXTRA_IMPORTS = "import ctypes\nimport struct"

SECCOMP_EXTRA_CODE = '''
SECCOMP_MODE_FILTER = 2
PR_SET_SECCOMP = 22
PR_SET_NO_NEW_PRIVS = 38
AUDIT_ARCH_X86_64 = 0xc000003e
AUDIT_ARCH_AARCH64 = 0xc00000b7
SECCOMP_RET_KILL_PROCESS = 0x80000000
SECCOMP_RET_ALLOW = 0x7fff0000
BPF_LD, BPF_W, BPF_ABS = 0x00, 0x00, 0x20
BPF_JMP, BPF_JEQ, BPF_K, BPF_RET = 0x05, 0x10, 0x00, 0x06

def bpf_stmt(code, k):
    return struct.pack("HBBI", code, 0, 0, k)

def bpf_jump(code, k, jt, jf):
    return struct.pack("HBBI", code, jt, jf, k)

SYSCALL_WHITELIST = {
    "x86_64": [0,1,2,3,5,8,9,10,11,12,13,14,15,16,17,20,21,22,24,25,28,32,33,39,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,63,72,79,80,89,97,99,102,104,105,107,108,110,111,115,131,137,140,158,186,202,204,217,218,228,229,230,231,232,233,234,257,262,273,281,284,285,290,291,292,293,302,318,334],
    "aarch64": [29,35,46,48,56,57,61,62,63,64,65,66,68,78,79,80,93,94,96,98,99,100,101,113,124,129,131,134,135,137,153,160,169,172,173,174,175,176,178,179,198,200,201,203,204,210,214,215,220,221,222,226,227,228,233,260,261,262,263,278,279,280,281,282,283,284,285,291],
}

def apply_seccomp_filter(allowed_syscalls=None):
    import platform
    arch = platform.machine()
    if arch == "arm64":
        arch = "aarch64"
    audit_arch = AUDIT_ARCH_X86_64 if arch == "x86_64" else AUDIT_ARCH_AARCH64
    syscalls = allowed_syscalls or SYSCALL_WHITELIST.get(arch, [])
    if not syscalls:
        return False

    bpf_filter = bpf_stmt(BPF_LD | BPF_W | BPF_ABS, 4)
    bpf_filter += bpf_jump(BPF_JMP | BPF_JEQ | BPF_K, audit_arch, 1, 0)
    bpf_filter += bpf_stmt(BPF_RET | BPF_K, SECCOMP_RET_KILL_PROCESS)
    bpf_filter += bpf_stmt(BPF_LD | BPF_W | BPF_ABS, 0)
    for sc in syscalls:
        bpf_filter += bpf_jump(BPF_JMP | BPF_JEQ | BPF_K, sc, 0, 1)
        bpf_filter += bpf_stmt(BPF_RET | BPF_K, SECCOMP_RET_ALLOW)
    bpf_filter += bpf_stmt(BPF_RET | BPF_K, SECCOMP_RET_KILL_PROCESS)

    class sock_filter(ctypes.Structure):
        _fields_ = [("code", ctypes.c_ushort), ("jt", ctypes.c_ubyte), ("jf", ctypes.c_ubyte), ("k", ctypes.c_uint)]
    class sock_fprog(ctypes.Structure):
        _fields_ = [("len", ctypes.c_ushort), ("filter", ctypes.POINTER(sock_filter))]

    n_insns = len(bpf_filter) // 8
    filter_array = (sock_filter * n_insns)()
    for i in range(n_insns):
        code, jt, jf, k = struct.unpack("HBBI", bpf_filter[i*8:(i+1)*8])
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
'''

SECCOMP_EXTRA_LIMITS = '''
    try:
        resource.setrlimit(resource.RLIMIT_NPROC, (50, 50))
    except (ValueError, resource.error):
        pass
    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
    except (ValueError, resource.error):
        pass'''

SECCOMP_PRE_EXECUTE = '''
    import platform
    if platform.system() == "Linux":
        try:
            apply_seccomp_filter(input_data.get("allowed_syscalls"))
        except Exception:
            pass'''


def _build_runner_script(level: SandboxLevel) -> str:
    """Build the runner script with appropriate security features."""
    if level == SandboxLevel.SECCOMP:
        return RUNNER_TEMPLATE.format(
            extra_imports=SECCOMP_EXTRA_IMPORTS,
            extra_code=SECCOMP_EXTRA_CODE,
            extra_limits=SECCOMP_EXTRA_LIMITS,
            pre_execute=SECCOMP_PRE_EXECUTE,
        )
    return RUNNER_TEMPLATE.format(
        extra_imports="",
        extra_code="",
        extra_limits="",
        pre_execute="",
    )


class SubprocessSandbox:
    """Execute tasks in isolated subprocess with resource limits."""

    def __init__(self, config: SandboxConfig):
        self.config = config
        self._runner_script = _build_runner_script(
            SandboxLevel.SECCOMP if config.level == SandboxLevel.SECCOMP else SandboxLevel.SUBPROCESS
        )

    def execute(
        self,
        code_str: Optional[str] = None,
        serialized_code: Optional[str] = None,
        task_input_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute code in an isolated subprocess.

        Args:
            code_str: Python code string containing a function definition.
            serialized_code: Base64-encoded cloudpickle serialized function.
            task_input_data: Input data to pass to the function.

        Returns:
            The result returned by the executed function.

        Raises:
            TimeoutError: If execution exceeds the configured timeout.
            SandboxError: If execution fails for any other reason.
        """
        input_data = {
            "code_str": code_str,
            "serialized_code": serialized_code,
            "task_input_data": task_input_data or {},
            "max_memory_mb": self.config.max_memory_mb,
            "max_cpu_time": self.config.max_cpu_time,
            "timeout": self.config.timeout,
        }
        if self.config.level == SandboxLevel.SECCOMP:
            input_data["allowed_syscalls"] = self.config.allowed_syscalls

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(self._runner_script)
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
            raise SandboxError(f"{result.get('error_type', 'Error')}: {result.get('error')}")
        finally:
            try:
                os.unlink(runner_path)
            except OSError:
                pass
