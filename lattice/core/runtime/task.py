"""
Task runtime representations for distributed task execution.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional, Type, Callable

from lattice.core.resource.node import SelectedNode
from lattice.core.workflow.base import TaskType


class TaskStatus(Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BaseTaskRuntime(ABC):
    workflow_id: str
    task_id: str
    resources: Dict[str, Any]
    status: TaskStatus = TaskStatus.READY
    object_ref: Any = None
    selected_node: Optional[SelectedNode] = None
    result: Optional[Any] = None
    error: Optional[str] = None

    @property
    @abstractmethod
    def task_type(self) -> TaskType:
        pass

    def set_status(self, status: TaskStatus) -> None:
        self.status = status

    def set_running(self, object_ref: Any, selected_node: SelectedNode) -> None:
        self.status = TaskStatus.RUNNING
        self.object_ref = object_ref
        self.selected_node = selected_node

    def set_completed(self, result: Any) -> None:
        self.status = TaskStatus.COMPLETED
        self.result = result

    def set_failed(self, error: str) -> None:
        self.status = TaskStatus.FAILED
        self.error = error

    def is_running(self) -> bool:
        return self.status == TaskStatus.RUNNING

    def is_completed(self) -> bool:
        return self.status == TaskStatus.COMPLETED

    def is_failed(self) -> bool:
        return self.status == TaskStatus.FAILED

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaseTaskRuntime":
        pass


@dataclass
class CodeTaskRuntime(BaseTaskRuntime):
    task_input: Dict[str, Any] = field(default_factory=dict)
    task_output: Dict[str, Any] = field(default_factory=dict)
    code_str: Optional[str] = None
    serialized_code: Optional[str] = None
    task_name: Optional[str] = None
    batch_config: Optional[Dict[str, Any]] = None

    @property
    def task_type(self) -> TaskType:
        return TaskType.CODE

    @property
    def is_batchable(self) -> bool:
        """Check if this task supports batching."""
        if not self.batch_config:
            return False
        return self.batch_config.get("enabled", False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_type": self.task_type.value,
            "workflow_id": self.workflow_id,
            "task_id": self.task_id,
            "task_name": self.task_name,
            "task_input": self.task_input,
            "task_output": self.task_output,
            "resources": self.resources,
            "code_str": self.code_str,
            "serialized_code": self.serialized_code,
            "batch_config": self.batch_config,
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CodeTaskRuntime":
        # Support both "serialized_code" (new) and "code_ser" (legacy) keys
        serialized_code = data.get("serialized_code") or data.get("code_ser")
        return cls(
            workflow_id=data["workflow_id"],
            task_id=data["task_id"],
            resources=data.get("resources", {}),
            task_input=data.get("task_input", {}),
            task_output=data.get("task_output", {}),
            code_str=data.get("code_str"),
            serialized_code=serialized_code,
            task_name=data.get("task_name"),
            batch_config=data.get("batch_config"),
        )


@dataclass
class LangGraphTaskRuntime(BaseTaskRuntime):
    serialized_code: str = ""
    serialized_args: str = ""
    serialized_kwargs: str = ""

    @property
    def task_type(self) -> TaskType:
        return TaskType.LANGGRAPH

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_type": self.task_type.value,
            "workflow_id": self.workflow_id,
            "task_id": self.task_id,
            "resources": self.resources,
            "serialized_code": self.serialized_code,
            "args": self.serialized_args,
            "kwargs": self.serialized_kwargs,
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LangGraphTaskRuntime":
        # Support both "serialized_code" (new) and "code_ser" (legacy) keys
        serialized_code = data.get("serialized_code") or data.get("code_ser", "")
        return cls(
            workflow_id=data["workflow_id"],
            task_id=data["task_id"],
            resources=data.get("resources", {}),
            serialized_code=serialized_code,
            serialized_args=data.get("args", ""),
            serialized_kwargs=data.get("kwargs", ""),
        )


class TaskRuntimeRegistry:
    _registry: Dict[str, Type[BaseTaskRuntime]] = {}

    @classmethod
    def register(cls, task_type: str, runtime_class: Type[BaseTaskRuntime]) -> None:
        cls._registry[task_type] = runtime_class

    @classmethod
    def get(cls, task_type: str) -> Optional[Type[BaseTaskRuntime]]:
        return cls._registry.get(task_type)

    @classmethod
    def create(cls, data: Dict[str, Any]) -> BaseTaskRuntime:
        task_type = data.get("task_type", TaskType.CODE.value)
        runtime_class = cls._registry.get(task_type)
        if runtime_class is None:
            raise ValueError(f"Unknown task type: {task_type}")
        return runtime_class.from_dict(data)


TaskRuntimeRegistry.register(TaskType.CODE.value, CodeTaskRuntime)
TaskRuntimeRegistry.register(TaskType.LANGGRAPH.value, LangGraphTaskRuntime)


def create_task_runtime(data: Dict[str, Any]) -> BaseTaskRuntime:
    return TaskRuntimeRegistry.create(data)
