"""
LangGraph client for running LangGraph workflows on Lattice.
"""
import base64
import functools
from typing import Any, Callable, Dict, Optional

import cloudpickle

from lattice.client.base import BaseClient


class LangGraphClient(BaseClient):
    """
    Client for running LangGraph workflows on Lattice.

    Inherits from BaseClient to provide common HTTP request functionality.
    """

    _VALID_RESOURCE_KEYS = {"cpu", "gpu", "cpu_mem", "gpu_mem"}

    def __init__(self, server_url: str = "http://localhost:8000"):
        """
        Initialize the LangGraph client.

        Args:
            server_url: The URL of the Lattice server.
        """
        super().__init__(server_url)
        self._default_resources = {"cpu": 1, "gpu": 0, "cpu_mem": 0, "gpu_mem": 0}

        response = self._post("/create_workflow")
        self.workflow_id = response["workflow_id"]

    def _merge_resources(self, resources: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge user-provided resources with defaults."""
        if resources is None:
            return self._default_resources.copy()

        invalid_keys = set(resources.keys()) - self._VALID_RESOURCE_KEYS
        if invalid_keys:
            raise ValueError(f"Invalid resource key(s): {', '.join(invalid_keys)}")

        merged = self._default_resources.copy()
        merged.update(resources)
        return merged

    def task(self, func_or_resources=None, *, resources: Optional[Dict[str, Any]] = None):
        if callable(func_or_resources):
            return self._decorate(func_or_resources, self._default_resources.copy())

        merged_resources = self._merge_resources(resources)
        return lambda func: self._decorate(func, merged_resources)

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
            "serialized_code": serialized_code,
            "resources": resources,
        })
        
        wrapper._task_id = response["task_id"]
        wrapper._is_lattice_task = True
        
        return wrapper
