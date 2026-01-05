"""
LangGraph client for running LangGraph workflows on Lattice.
"""
import base64
import functools
from typing import Any, Callable, Dict, Optional

import cloudpickle
import requests


class LangGraphClient:
    def __init__(self, server_url: str = "http://localhost:8000"):
        self.server_url = server_url.rstrip("/")
        self._default_resources = {"cpu": 1, "gpu": 0, "cpu_mem": 0, "gpu_mem": 0}
        
        response = self._post("/create_workflow")
        self.workflow_id = response["workflow_id"]

    def _post(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.server_url}{endpoint}"
        response = requests.post(url, json=data or {})
        
        if response.status_code != 200:
            raise Exception(f"Request failed: {response.status_code}, {response.text}")
        
        return response.json()

    def task(self, func_or_resources=None, *, resources: Optional[Dict[str, Any]] = None):
        if callable(func_or_resources):
            return self._decorate(func_or_resources, self._default_resources)
        
        if resources is None:
            resources = self._default_resources
        else:
            for key in resources:
                if key not in ["cpu", "gpu", "cpu_mem", "gpu_mem"]:
                    raise ValueError(f"Invalid resource key: {key}")
            
            merged = self._default_resources.copy()
            merged.update(resources)
            resources = merged
        
        return lambda func: self._decorate(func, resources)

    def _decorate(self, func: Callable, resources: Dict[str, Any]) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            payload = {
                "workflow_id": self.workflow_id,
                "task_id": wrapper._task_id,
                "args": base64.b64encode(cloudpickle.dumps(args)).decode("utf-8"),
                "kwargs": base64.b64encode(cloudpickle.dumps(kwargs)).decode("utf-8"),
            }
            
            try:
                response = self._post("/run_langgraph_task", payload)
                return response.get("result")
            except Exception as e:
                raise RuntimeError(f"Failed to execute task: {e}")
        
        serialized_code = base64.b64encode(cloudpickle.dumps(func)).decode("utf-8")
        
        response = self._post("/add_langgraph_task", {
            "workflow_id": self.workflow_id,
            "task_type": "langgraph",
            "task_name": func.__name__,
            "code_ser": serialized_code,
            "resources": resources,
        })
        
        wrapper._task_id = response["task_id"]
        wrapper._is_lattice_task = True
        
        return wrapper
