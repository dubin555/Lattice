"""
Task execution runner for distributed task execution.
"""
import logging
import os
from typing import Any, Dict, Optional

import ray

from lattice.executor.sandbox import (
    SandboxExecutor,
    SandboxConfig,
    SandboxLevel,
    get_sandbox_config,
)
from lattice.executor.code_executor import (
    execute_code_string,
    execute_task,
    execute_serialized_with_serialized_args,
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

    config = SandboxConfig(level=SandboxLevel(sandbox_level)) if sandbox_level else get_sandbox_config()

    if config.level != SandboxLevel.NONE:
        return SandboxExecutor(config).execute(code_str, serialized_code, task_input_data)

    return execute_task(code_str, serialized_code, task_input_data)


@ray.remote(max_retries=0)
def execute_langgraph_task(
    serialized_code: str,
    serialized_args: str,
    serialized_kwargs: str,
    cuda_visible_devices: Optional[str] = None,
) -> Any:
    if cuda_visible_devices:
        os.environ["CUDA_VISIBLE_DEVICES"] = cuda_visible_devices
    return execute_serialized_with_serialized_args(
        serialized_code, serialized_args, serialized_kwargs
    )


class CodeRunner:
    def __init__(self, code_str: str, task_input_data: Optional[Dict[str, Any]] = None):
        self.code_str = code_str
        self.task_input_data = task_input_data or {}

    def run(self) -> Dict[str, Any]:
        return execute_code_string(self.code_str, self.task_input_data)


def _build_ray_options(resources: Dict[str, Any], node_id: Optional[str]) -> Dict[str, Any]:
    num_cpus = resources.get("cpu", 1)
    num_gpus = resources.get("gpu", 0)
    memory = resources.get("cpu_mem", 0)
    options = {"num_cpus": num_cpus}
    if memory > 0:
        options["memory"] = memory
    if num_gpus > 0:
        options["num_gpus"] = num_gpus
    if node_id:
        options["scheduling_strategy"] = ray.util.scheduling_strategies.NodeAffinitySchedulingStrategy(
            node_id=node_id, soft=False
        )
    return options


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
        options = _build_ray_options(resources or {}, node_id)
        cuda_devices = str(gpu_id) if gpu_id is not None else None
        return execute_code_task.options(**options).remote(
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
        options = _build_ray_options(resources or {}, node_id)
        cuda_devices = str(gpu_id) if gpu_id is not None else None
        return execute_langgraph_task.options(**options).remote(
            serialized_code=serialized_code,
            serialized_args=serialized_args,
            serialized_kwargs=serialized_kwargs,
            cuda_visible_devices=cuda_devices,
        )
