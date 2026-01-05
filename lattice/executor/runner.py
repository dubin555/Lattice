"""
Task execution runner for distributed task execution.
"""
import ast
import base64
import logging
import os
from typing import Dict, Any, Optional, Callable

import cloudpickle
import ray

from lattice.executor.sandbox import (
    SandboxExecutor,
    SandboxConfig,
    SandboxLevel,
    get_sandbox_config,
)

logger = logging.getLogger(__name__)


@ray.remote(max_retries=0)
def execute_code_task(
    code_str: Optional[str] = None,
    serialized_code: Optional[str] = None,
    task_input_data: Optional[Dict[str, Any]] = None,
    cuda_visible_devices: Optional[str] = None,
    sandbox_level: Optional[str] = None,
) -> Dict[str, Any]:
    if cuda_visible_devices:
        os.environ["CUDA_VISIBLE_DEVICES"] = cuda_visible_devices

    if sandbox_level is None:
        config = get_sandbox_config()
    else:
        config = SandboxConfig(level=SandboxLevel(sandbox_level))
    
    if config.level != SandboxLevel.NONE:
        executor = SandboxExecutor(config)
        return executor.execute(code_str, serialized_code, task_input_data)
    
    if serialized_code is not None:
        func = cloudpickle.loads(base64.b64decode(serialized_code))
        return func(task_input_data)
    elif code_str is not None:
        runner = CodeRunner(code_str, task_input_data)
        return runner.run()
    else:
        raise ValueError("Either code_str or serialized_code must be provided")


@ray.remote(max_retries=0)
def execute_langgraph_task(
    serialized_code: str,
    serialized_args: str,
    serialized_kwargs: str,
    cuda_visible_devices: Optional[str] = None,
) -> Any:
    if cuda_visible_devices:
        os.environ["CUDA_VISIBLE_DEVICES"] = cuda_visible_devices

    func = cloudpickle.loads(base64.b64decode(serialized_code))
    args = cloudpickle.loads(base64.b64decode(serialized_args))
    kwargs = cloudpickle.loads(base64.b64decode(serialized_kwargs))

    return func(*args, **kwargs)


class CodeRunner:
    def __init__(self, code_str: str, task_input_data: Optional[Dict[str, Any]] = None):
        self.code_str = code_str
        self.task_input_data = task_input_data or {}

    def _extract_imports(self) -> list:
        tree = ast.parse(self.code_str)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                imports.append(node)
        return imports

    def _extract_function(self) -> Optional[ast.FunctionDef]:
        tree = ast.parse(self.code_str)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                return node
        return None

    def run(self) -> Dict[str, Any]:
        func_node = self._extract_function()
        if func_node is None:
            raise ValueError("No function definition found in code")

        import_nodes = self._extract_imports()
        namespace: Dict[str, Any] = {}

        for imp in import_nodes:
            module = ast.Module(body=[imp], type_ignores=[])
            code = compile(module, '<string>', 'exec')
            exec(code, namespace)

        module = ast.Module(body=[func_node], type_ignores=[])
        code = compile(module, '<string>', 'exec')
        exec(code, namespace)

        func_name = func_node.name
        if func_name not in namespace:
            raise NameError(f"Function {func_name} not found in namespace")

        return namespace[func_name](self.task_input_data)


class TaskExecutor:
    @staticmethod
    def submit_code_task(
        task_input_data: Dict[str, Any],
        code_str: Optional[str] = None,
        serialized_code: Optional[str] = None,
        resources: Optional[Dict[str, Any]] = None,
        node_id: Optional[str] = None,
        gpu_id: Optional[int] = None,
        sandbox_level: Optional[str] = None,
    ) -> ray.ObjectRef:
        resources = resources or {}
        num_cpus = resources.get("cpu", 1)
        num_gpus = resources.get("gpu", 0)
        memory = resources.get("cpu_mem", 0)

        options = {
            "num_cpus": num_cpus,
            "memory": memory if memory > 0 else None,
        }

        if num_gpus > 0:
            options["num_gpus"] = num_gpus

        if node_id:
            options["scheduling_strategy"] = ray.util.scheduling_strategies.NodeAffinitySchedulingStrategy(
                node_id=node_id,
                soft=False,
            )

        cuda_devices = str(gpu_id) if gpu_id is not None else None

        return execute_code_task.options(**{k: v for k, v in options.items() if v is not None}).remote(
            code_str=code_str,
            serialized_code=serialized_code,
            task_input_data=task_input_data,
            cuda_visible_devices=cuda_devices,
            sandbox_level=sandbox_level,
        )

    @staticmethod
    def submit_langgraph_task(
        serialized_code: str,
        serialized_args: str,
        serialized_kwargs: str,
        resources: Optional[Dict[str, Any]] = None,
        node_id: Optional[str] = None,
        gpu_id: Optional[int] = None,
    ) -> ray.ObjectRef:
        resources = resources or {}
        num_cpus = resources.get("cpu", 1)
        num_gpus = resources.get("gpu", 0)
        memory = resources.get("cpu_mem", 0)

        options = {
            "num_cpus": num_cpus,
            "memory": memory if memory > 0 else None,
        }

        if num_gpus > 0:
            options["num_gpus"] = num_gpus

        if node_id:
            options["scheduling_strategy"] = ray.util.scheduling_strategies.NodeAffinitySchedulingStrategy(
                node_id=node_id,
                soft=False,
            )

        cuda_devices = str(gpu_id) if gpu_id is not None else None

        return execute_langgraph_task.options(**{k: v for k, v in options.items() if v is not None}).remote(
            serialized_code=serialized_code,
            serialized_args=serialized_args,
            serialized_kwargs=serialized_kwargs,
            cuda_visible_devices=cuda_devices,
        )
