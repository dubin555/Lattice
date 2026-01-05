"""
Core module for Lattice.
"""
from lattice.core.resource.node import Node, NodeResources, GpuResource, NodeStatus, SelectedNode
from lattice.core.resource.manager import ResourceManager, TaskResourceRequirements
from lattice.core.runtime.task import (
    TaskStatus as RuntimeTaskStatus,
    BaseTaskRuntime,
    CodeTaskRuntime,
    LangGraphTaskRuntime,
    TaskRuntimeRegistry,
    create_task_runtime,
)
from lattice.core.runtime.workflow import WorkflowRuntime, WorkflowRuntimeManager
from lattice.core.workflow.base import (
    TaskType,
    BaseTask,
    CodeTask,
    LangGraphTask,
    BaseWorkflow,
    Workflow,
    LangGraphWorkflow,
    DEFAULT_RESOURCES,
)
from lattice.core.scheduler.message_bus import Message, MessageType, MessageBus

__all__ = [
    "Node",
    "NodeResources",
    "GpuResource",
    "NodeStatus",
    "SelectedNode",
    "ResourceManager",
    "TaskResourceRequirements",
    "RuntimeTaskStatus",
    "BaseTaskRuntime",
    "CodeTaskRuntime",
    "LangGraphTaskRuntime",
    "TaskRuntimeRegistry",
    "create_task_runtime",
    "WorkflowRuntime",
    "WorkflowRuntimeManager",
    "TaskType",
    "BaseTask",
    "CodeTask",
    "LangGraphTask",
    "BaseWorkflow",
    "Workflow",
    "LangGraphWorkflow",
    "DEFAULT_RESOURCES",
    "Message",
    "MessageType",
    "MessageBus",
]


def __getattr__(name: str):
    if name == "Orchestrator":
        from lattice.core.orchestrator import Orchestrator
        return Orchestrator
    elif name == "Scheduler":
        from lattice.core.scheduler import Scheduler
        return Scheduler
    elif name == "Worker":
        from lattice.core.worker import Worker
        return Worker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
