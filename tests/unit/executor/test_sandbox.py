"""
Unit tests for sandbox execution module.
"""
import platform
import pytest

from lattice.executor.sandbox import (
    SandboxLevel,
    SandboxConfig,
    SandboxExecutor,
    SandboxError,
    SubprocessSandbox,
    set_sandbox_config,
    get_sandbox_config,
    get_sandbox_executor,
)


class TestSandboxConfig:
    def test_default_config(self):
        config = SandboxConfig()
        assert config.level == SandboxLevel.SUBPROCESS
        assert config.timeout == 300
        assert config.max_memory_mb == 2048

    def test_custom_config(self):
        config = SandboxConfig(
            level=SandboxLevel.SECCOMP,
            timeout=60,
            max_memory_mb=512,
        )
        assert config.level == SandboxLevel.SECCOMP
        assert config.timeout == 60
        assert config.max_memory_mb == 512

    def test_sandbox_levels(self):
        assert SandboxLevel.NONE.value == "none"
        assert SandboxLevel.SUBPROCESS.value == "subprocess"
        assert SandboxLevel.SECCOMP.value == "seccomp"
        assert SandboxLevel.DOCKER.value == "docker"


class TestSandboxExecutorDirect:
    def test_direct_execution_with_code_str(self):
        config = SandboxConfig(level=SandboxLevel.NONE)
        executor = SandboxExecutor(config)
        
        code = """
def my_task(params):
    return {"result": params.get("x", 0) * 2}
"""
        result = executor.execute(code_str=code, task_input_data={"x": 5})
        assert result == {"result": 10}

    def test_direct_execution_no_code_raises(self):
        config = SandboxConfig(level=SandboxLevel.NONE)
        executor = SandboxExecutor(config)
        
        with pytest.raises(ValueError, match="No code provided"):
            executor.execute()


class TestSubprocessSandbox:
    def test_subprocess_simple_execution(self):
        config = SandboxConfig(level=SandboxLevel.SUBPROCESS, timeout=30)
        sandbox = SubprocessSandbox(config)
        
        code = """
def task(params):
    return {"sum": params.get("a", 0) + params.get("b", 0)}
"""
        result = sandbox.execute(code_str=code, task_input_data={"a": 3, "b": 4})
        assert result == {"sum": 7}

    def test_subprocess_with_imports(self):
        config = SandboxConfig(level=SandboxLevel.SUBPROCESS, timeout=30)
        sandbox = SubprocessSandbox(config)
        
        code = """
import json

def task(params):
    return {"json": json.dumps(params)}
"""
        result = sandbox.execute(code_str=code, task_input_data={"key": "value"})
        assert result == {"json": '{"key": "value"}'}

    def test_subprocess_exception_handling(self):
        config = SandboxConfig(level=SandboxLevel.SUBPROCESS, timeout=30)
        sandbox = SubprocessSandbox(config)
        
        code = """
def task(params):
    raise ValueError("test error")
"""
        with pytest.raises(SandboxError, match="ValueError.*test error"):
            sandbox.execute(code_str=code, task_input_data={})

    def test_subprocess_no_function_raises(self):
        config = SandboxConfig(level=SandboxLevel.SUBPROCESS, timeout=30)
        sandbox = SubprocessSandbox(config)
        
        code = "x = 1 + 2"
        with pytest.raises(SandboxError, match="No function definition"):
            sandbox.execute(code_str=code, task_input_data={})


class TestSeccompSandbox:
    def test_seccomp_simple_execution(self):
        config = SandboxConfig(level=SandboxLevel.SECCOMP, timeout=30)
        sandbox = SubprocessSandbox(config)
        
        code = """
def task(params):
    return {"value": params.get("x", 0) ** 2}
"""
        result = sandbox.execute(code_str=code, task_input_data={"x": 4})
        assert result == {"value": 16}

    def test_seccomp_with_math(self):
        config = SandboxConfig(level=SandboxLevel.SECCOMP, timeout=30)
        sandbox = SubprocessSandbox(config)
        
        code = """
import math

def task(params):
    return {"sqrt": math.sqrt(params.get("n", 0))}
"""
        result = sandbox.execute(code_str=code, task_input_data={"n": 16})
        assert result == {"sqrt": 4.0}

    def test_seccomp_exception_handling(self):
        config = SandboxConfig(level=SandboxLevel.SECCOMP, timeout=30)
        sandbox = SubprocessSandbox(config)
        
        code = """
def task(params):
    return 1 / 0
"""
        with pytest.raises(SandboxError, match="ZeroDivisionError"):
            sandbox.execute(code_str=code, task_input_data={})


class TestSandboxExecutorIntegration:
    def test_executor_subprocess_level(self):
        config = SandboxConfig(level=SandboxLevel.SUBPROCESS, timeout=30)
        executor = SandboxExecutor(config)
        
        code = """
def task(params):
    return {"msg": "hello from subprocess"}
"""
        result = executor.execute(code_str=code, task_input_data={})
        assert result == {"msg": "hello from subprocess"}

    def test_executor_seccomp_level(self):
        config = SandboxConfig(level=SandboxLevel.SECCOMP, timeout=30)
        executor = SandboxExecutor(config)
        
        code = """
def task(params):
    return {"msg": "hello from seccomp"}
"""
        result = executor.execute(code_str=code, task_input_data={})
        assert result == {"msg": "hello from seccomp"}


class TestGlobalSandboxConfig:
    def test_set_and_get_config(self):
        config = SandboxConfig(level=SandboxLevel.SECCOMP, timeout=120)
        set_sandbox_config(config)
        
        retrieved = get_sandbox_config()
        assert retrieved.level == SandboxLevel.SECCOMP
        assert retrieved.timeout == 120

    def test_get_sandbox_executor(self):
        config = SandboxConfig(level=SandboxLevel.SUBPROCESS)
        set_sandbox_config(config)
        
        executor = get_sandbox_executor()
        assert executor.config.level == SandboxLevel.SUBPROCESS


class TestSandboxResourceLimits:
    def test_memory_limit_config(self):
        config = SandboxConfig(max_memory_mb=256)
        assert config.max_memory_mb == 256

    def test_cpu_time_limit_config(self):
        config = SandboxConfig(max_cpu_time=60)
        assert config.max_cpu_time == 60

    def test_allowed_syscalls_config(self):
        config = SandboxConfig(allowed_syscalls=[0, 1, 2, 3])
        assert config.allowed_syscalls == [0, 1, 2, 3]
