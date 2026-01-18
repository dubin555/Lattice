"""
Docker-based sandbox execution.

Provides the strongest isolation by running tasks in Docker containers
with strict resource limits, network isolation, and read-only filesystem.

Note: The embedded runner script (DOCKER_RUNNER_SCRIPT) contains execute_code
logic that is derived from the utilities in code_executor.py. This script must
remain self-contained since Docker containers don't have access to the main
Lattice codebase.
"""
import os
import json
import tempfile
import subprocess
from typing import Dict, Any, Optional

from lattice.executor.sandbox.base import (
    SandboxConfig,
    SandboxError,
    TimeoutError,
)


# DOCKER_RUNNER_SCRIPT: Self-contained Python script for Docker container execution.
# The execute_code function below is derived from lattice.executor.code_executor
# but must be embedded here since Docker containers don't have access to the Lattice package.
DOCKER_RUNNER_SCRIPT = '''
import sys
import json
import base64

def execute_code(serialized_code, code_str, task_input_data):
    if serialized_code:
        import cloudpickle
        return cloudpickle.loads(base64.b64decode(serialized_code))(task_input_data)
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
            exec(compile(ast.Module(body=[imp], type_ignores=[]), '<string>', 'exec'), namespace)
        exec(compile(ast.Module(body=[func_node], type_ignores=[]), '<string>', 'exec'), namespace)
        return namespace[func_node.name](task_input_data)
    raise ValueError("No code provided")

input_data = json.loads(sys.stdin.read())
try:
    result = execute_code(input_data.get("serialized_code"), input_data.get("code_str"), input_data.get("task_input_data", {}))
    print(json.dumps({"success": True, "result": result}))
except Exception as e:
    print(json.dumps({"success": False, "error": str(e), "error_type": type(e).__name__}))
    sys.exit(1)
'''


class DockerSandbox:
    """Execute tasks in isolated Docker containers."""

    def __init__(self, config: SandboxConfig):
        self.config = config
        self._check_docker()

    def _check_docker(self) -> None:
        """Verify Docker is available and working."""
        try:
            subprocess.run(["docker", "version"], capture_output=True, check=True, timeout=10)
        except (subprocess.SubprocessError, FileNotFoundError):
            raise SandboxError("Docker is not available.")

    def execute(
        self,
        code_str: Optional[str] = None,
        serialized_code: Optional[str] = None,
        task_input_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute code in an isolated Docker container.

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
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(DOCKER_RUNNER_SCRIPT)
            runner_path = f.name
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(input_data, f)
            input_path = f.name

        try:
            docker_cmd = [
                "docker", "run", "--rm", "-i",
                f"--memory={self.config.max_memory_mb}m", "--cpus=1",
                "--pids-limit=100", "--read-only", "--tmpfs=/tmp:size=100m",
            ]
            if not self.config.network_enabled:
                docker_cmd.append("--network=none")
            docker_cmd.extend(["--security-opt=no-new-privileges", "--cap-drop=ALL"])
            docker_cmd.extend(["-v", f"{runner_path}:/app/runner.py:ro"])
            for host, cont in self.config.mount_paths.items():
                docker_cmd.extend(["-v", f"{host}:{cont}:ro"])
            docker_cmd.extend([self.config.docker_image, "python", "/app/runner.py"])

            with open(input_path, 'r') as inp:
                process = subprocess.Popen(docker_cmd, stdin=inp, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                stdout, stderr = process.communicate(timeout=self.config.timeout + 30)
            except subprocess.TimeoutExpired:
                process.kill()
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
            raise SandboxError(f"{result.get('error_type', 'Error')}: {result.get('error')}")
        finally:
            try:
                os.unlink(runner_path)
                os.unlink(input_path)
            except OSError:
                pass
