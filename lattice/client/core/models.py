"""
Client models for task and workflow management.
"""
from dataclasses import dataclass
from typing import Dict, List, Any, Optional

# Separator used in task output references
# Format: "{task_id}.output.{output_key}"
TASK_REFERENCE_SEPARATOR = ".output."


@dataclass
class TaskOutput:
    task_id: str
    output_key: str

    def to_reference_string(self) -> str:
        return f"{self.task_id}{TASK_REFERENCE_SEPARATOR}{self.output_key}"


class TaskOutputs:
    def __init__(self, task_id: str, output_keys: List[str]):
        self._task_id = task_id
        self._outputs: Dict[str, TaskOutput] = {
            key: TaskOutput(task_id=task_id, output_key=key)
            for key in output_keys
        }
    
    def __getitem__(self, key: str) -> TaskOutput:
        if key not in self._outputs:
            raise KeyError(f"Output '{key}' not found. Available outputs: {list(self._outputs.keys())}")
        return self._outputs[key]
    
    def __contains__(self, key: str) -> bool:
        return key in self._outputs
    
    def keys(self) -> List[str]:
        return list(self._outputs.keys())


@dataclass
class LatticeTask:
    task_id: str
    workflow_id: str
    server_url: str
    task_name: str
    outputs: TaskOutputs
    
    def __init__(
        self,
        task_id: str,
        workflow_id: str,
        server_url: str,
        task_name: str,
        output_keys: Optional[List[str]] = None,
    ):
        self.task_id = task_id
        self.workflow_id = workflow_id
        self.server_url = server_url
        self.task_name = task_name
        self.outputs = TaskOutputs(task_id, output_keys or [])
