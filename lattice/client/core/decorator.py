"""
Task decorator for defining task metadata.
"""
import base64
import inspect
from dataclasses import dataclass
from typing import Callable, Dict, List, Any, Optional

import cloudpickle

from lattice.config.defaults import get_default_resources


@dataclass
class TaskMetadata:
    func: Callable
    func_name: str
    code_str: str
    serialized_code: str
    inputs: List[str]
    outputs: List[str]
    resources: Dict[str, Any]
    data_types: Dict[str, str]


def normalize_resources(resources: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    default_resources = get_default_resources()
    
    if resources is None:
        return default_resources.copy()
    
    normalized = default_resources.copy()
    for key in ["cpu", "cpu_mem", "gpu", "gpu_mem"]:
        if key in resources:
            normalized[key] = resources[key]
    
    if normalized["cpu"] < 1:
        normalized["cpu"] = 1
    
    if normalized["gpu_mem"] > 0 and normalized["gpu"] < 1:
        normalized["gpu"] = 1
    
    return normalized


def task(
    inputs: List[str],
    outputs: List[str],
    resources: Optional[Dict[str, Any]] = None,
    data_types: Optional[Dict[str, str]] = None,
):
    def decorator(func: Callable) -> Callable:
        source_lines = inspect.getsourcelines(func)[0]
        
        func_start_idx = 0
        for idx, line in enumerate(source_lines):
            if line.strip().startswith("def "):
                func_start_idx = idx
                break
        
        func_lines = source_lines[func_start_idx:]
        code_str = "".join(func_lines)
        
        serialized_code = base64.b64encode(cloudpickle.dumps(func)).decode("utf-8")
        
        resources_config = normalize_resources(resources)
        
        if data_types is None:
            types_config = {param: "str" for param in inputs + outputs}
        else:
            types_config = {param: "str" for param in inputs + outputs}
            types_config.update(data_types)
        
        metadata = TaskMetadata(
            func=func,
            func_name=func.__name__,
            code_str=code_str,
            serialized_code=serialized_code,
            inputs=inputs,
            outputs=outputs,
            resources=resources_config,
            data_types=types_config,
        )
        
        func._lattice_task_metadata = metadata
        return func
    
    return decorator


def get_task_metadata(func: Callable) -> TaskMetadata:
    if not hasattr(func, "_lattice_task_metadata"):
        raise ValueError(f"Function {func.__name__} is not decorated with @task")
    return func._lattice_task_metadata
