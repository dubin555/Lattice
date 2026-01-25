"""
Tests for code execution consistency across different execution paths.

The Lattice codebase has code execution logic in multiple places:
- lattice/executor/code_executor.py (canonical implementation)
- lattice/executor/sandbox/subprocess.py RUNNER_TEMPLATE (embedded for isolation)

These tests verify that all implementations produce consistent results.
"""
import base64
import pytest
import cloudpickle

from lattice.executor.code_executor import (
    execute_code_string,
    execute_serialized,
    execute_task,
)
from lattice.executor.sandbox.subprocess import SubprocessSandbox
from lattice.executor.sandbox.base import SandboxConfig, SandboxLevel


class TestCodeExecutorConsistency:
    """Verify code_executor produces expected results."""

    def test_execute_code_string_simple(self):
        """Simple code string execution."""
        code_str = """
def process(data):
    return {"result": data.get("x", 0) * 2}
"""
        result = execute_code_string(code_str, {"x": 5})
        assert result == {"result": 10}

    def test_execute_code_string_with_import(self):
        """Code string with import statements."""
        code_str = """
import math

def calculate(data):
    return {"sqrt": math.sqrt(data["value"])}
"""
        result = execute_code_string(code_str, {"value": 16})
        assert result == {"sqrt": 4.0}

    def test_execute_serialized_function(self):
        """Serialized function execution."""
        def double_value(data):
            return {"doubled": data.get("n", 0) * 2}

        serialized = base64.b64encode(cloudpickle.dumps(double_value)).decode("utf-8")
        result = execute_serialized(serialized, {"n": 7})
        assert result == {"doubled": 14}

    def test_execute_task_with_code_str(self):
        """execute_task with code string."""
        code_str = """
def add(data):
    return {"sum": data["a"] + data["b"]}
"""
        result = execute_task(code_str=code_str, task_input_data={"a": 3, "b": 4})
        assert result == {"sum": 7}

    def test_execute_task_with_serialized_code(self):
        """execute_task with serialized code."""
        def multiply(data):
            return {"product": data["x"] * data["y"]}

        serialized = base64.b64encode(cloudpickle.dumps(multiply)).decode("utf-8")
        result = execute_task(serialized_code=serialized, task_input_data={"x": 6, "y": 7})
        assert result == {"product": 42}


class TestSubprocessRunnerConsistency:
    """Verify subprocess runner produces same results as code_executor."""

    @pytest.fixture
    def sandbox(self):
        """Create a subprocess sandbox with default config."""
        config = SandboxConfig(
            level=SandboxLevel.SUBPROCESS,
            timeout=30,
            max_memory_mb=512,
            max_cpu_time=30,
        )
        return SubprocessSandbox(config)

    def test_subprocess_code_string_matches_direct(self, sandbox):
        """Subprocess and direct execution produce same result for code string."""
        code_str = """
def compute(data):
    return {"result": data.get("value", 0) ** 2}
"""
        task_input = {"value": 5}

        # Direct execution
        direct_result = execute_code_string(code_str, task_input)

        # Subprocess execution
        subprocess_result = sandbox.execute(code_str=code_str, task_input_data=task_input)

        assert subprocess_result == direct_result

    def test_subprocess_serialized_matches_direct(self, sandbox):
        """Subprocess and direct execution produce same result for serialized code."""
        def cube(data):
            return {"cubed": data.get("n", 0) ** 3}

        serialized = base64.b64encode(cloudpickle.dumps(cube)).decode("utf-8")
        task_input = {"n": 3}

        # Direct execution
        direct_result = execute_serialized(serialized, task_input)

        # Subprocess execution
        subprocess_result = sandbox.execute(serialized_code=serialized, task_input_data=task_input)

        assert subprocess_result == direct_result

    def test_subprocess_with_imports_matches_direct(self, sandbox):
        """Subprocess handles imports the same as direct execution."""
        code_str = """
import json

def process(data):
    serialized = json.dumps(data)
    return {"length": len(serialized)}
"""
        task_input = {"key": "value", "count": 42}

        # Direct execution
        direct_result = execute_code_string(code_str, task_input)

        # Subprocess execution
        subprocess_result = sandbox.execute(code_str=code_str, task_input_data=task_input)

        assert subprocess_result == direct_result


class TestRunnerTemplateLogicVerification:
    """Verify RUNNER_TEMPLATE contains critical execute_code logic."""

    def test_runner_template_has_cloudpickle_deserialization(self):
        """RUNNER_TEMPLATE should deserialize cloudpickle functions."""
        from lattice.executor.sandbox.subprocess import RUNNER_TEMPLATE

        assert "cloudpickle.loads(base64.b64decode(serialized_code))" in RUNNER_TEMPLATE

    def test_runner_template_has_ast_parsing(self):
        """RUNNER_TEMPLATE should parse code strings with AST."""
        from lattice.executor.sandbox.subprocess import RUNNER_TEMPLATE

        assert "ast.parse(code_str)" in RUNNER_TEMPLATE
        assert "ast.FunctionDef" in RUNNER_TEMPLATE

    def test_runner_template_handles_imports(self):
        """RUNNER_TEMPLATE should handle import statements in code."""
        from lattice.executor.sandbox.subprocess import RUNNER_TEMPLATE

        assert "ast.Import" in RUNNER_TEMPLATE or "ast.ImportFrom" in RUNNER_TEMPLATE

    def test_runner_template_executes_in_namespace(self):
        """RUNNER_TEMPLATE should execute function in a namespace."""
        from lattice.executor.sandbox.subprocess import RUNNER_TEMPLATE

        assert "namespace" in RUNNER_TEMPLATE
        assert "exec(compile(" in RUNNER_TEMPLATE
