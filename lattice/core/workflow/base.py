"""
Base workflow and task definitions.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Optional, Type
import networkx as nx

from lattice.config.defaults import get_default_resources


class TaskType(Enum):
    CODE = "code"
    LANGGRAPH = "langgraph"


DEFAULT_RESOURCES: Dict[str, Any] = get_default_resources()


@dataclass
class BaseTask(ABC):
    workflow_id: str
    task_id: str
    task_name: str
    completed: bool = False

    @property
    @abstractmethod
    def task_type(self) -> TaskType:
        pass

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        pass


@dataclass
class CodeTask(BaseTask):
    resources: Optional[Dict[str, Any]] = None
    task_input: Optional[Dict[str, Any]] = None
    task_output: Optional[Dict[str, Any]] = None
    code_str: Optional[str] = None
    serialized_code: Optional[str] = None
    batch_config: Optional[Dict[str, Any]] = None

    @property
    def task_type(self) -> TaskType:
        return TaskType.CODE

    def save(
        self,
        task_input: Dict[str, Any],
        task_output: Dict[str, Any],
        code_str: Optional[str] = None,
        serialized_code: Optional[str] = None,
        resources: Optional[Dict[str, Any]] = None,
        batch_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.task_input = task_input
        self.task_output = task_output
        self.code_str = code_str
        self.serialized_code = serialized_code
        self.resources = resources or DEFAULT_RESOURCES.copy()
        self.batch_config = batch_config

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
            "code_ser": self.serialized_code,
            "batch_config": self.batch_config,
        }


@dataclass
class LangGraphTask(BaseTask):
    serialized_code: str = ""
    resources: Dict[str, Any] = field(default_factory=lambda: DEFAULT_RESOURCES.copy())
    serialized_args: Optional[str] = None
    serialized_kwargs: Optional[str] = None

    @property
    def task_type(self) -> TaskType:
        return TaskType.LANGGRAPH

    def set_args(self, args: str) -> None:
        self.serialized_args = args

    def set_kwargs(self, kwargs: str) -> None:
        self.serialized_kwargs = kwargs

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_type": self.task_type.value,
            "workflow_id": self.workflow_id,
            "task_id": self.task_id,
            "task_name": self.task_name,
            "resources": self.resources,
            "code_ser": self.serialized_code,
            "args": self.serialized_args,
            "kwargs": self.serialized_kwargs,
        }


class BaseWorkflow(ABC):
    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id
        self._tasks: Dict[str, BaseTask] = {}

    @property
    def task_count(self) -> int:
        return len(self._tasks)

    def get_task(self, task_id: str) -> Optional[BaseTask]:
        return self._tasks.get(task_id)

    def add_task(self, task_id: str, task: BaseTask) -> None:
        if task_id != task.task_id:
            raise ValueError("task_id must match task.task_id")
        self._tasks[task_id] = task

    def remove_task(self, task_id: str) -> None:
        if task_id in self._tasks:
            del self._tasks[task_id]

    def get_all_tasks(self) -> List[BaseTask]:
        return list(self._tasks.values())

    def get_task_info_list(self) -> List[Dict[str, str]]:
        return [
            {"id": task_id, "name": task.task_name}
            for task_id, task in self._tasks.items()
        ]


class Workflow(BaseWorkflow):
    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id
        self._tasks: Dict[str, CodeTask] = {}
        self._graph: nx.DiGraph = nx.DiGraph()

    def add_task(self, task_id: str, task: CodeTask) -> None:
        if task_id != task.task_id:
            raise ValueError("task_id must match task.task_id")
        self._tasks[task_id] = task
        self._graph.add_node(task_id)

    def remove_task(self, task_id: str) -> None:
        if task_id in self._tasks:
            del self._tasks[task_id]
        if task_id in self._graph:
            self._graph.remove_node(task_id)

    def add_edge(self, source_task_id: str, target_task_id: str) -> None:
        if source_task_id not in self._graph or target_task_id not in self._graph:
            raise ValueError("Both tasks must exist before adding an edge")
        
        self._graph.add_edge(source_task_id, target_task_id)
        
        if not nx.is_directed_acyclic_graph(self._graph):
            self._graph.remove_edge(source_task_id, target_task_id)
            raise ValueError("Adding this edge would create a cycle")

    def remove_edge(self, source_task_id: str, target_task_id: str) -> None:
        if self._graph.has_edge(source_task_id, target_task_id):
            self._graph.remove_edge(source_task_id, target_task_id)

    def get_start_tasks(self) -> List[CodeTask]:
        start_nodes = [
            node for node in self._graph.nodes
            if self._graph.in_degree(node) == 0
        ]
        return [self._tasks[node] for node in start_nodes if node in self._tasks]

    def get_ready_tasks_after_completion(self, completed_task_id: str) -> List[CodeTask]:
        if completed_task_id not in self._tasks:
            return []
        
        self._tasks[completed_task_id].completed = True
        ready_tasks = []
        
        for successor_id in self._graph.successors(completed_task_id):
            all_predecessors_completed = all(
                self._tasks[pred_id].completed
                for pred_id in self._graph.predecessors(successor_id)
                if pred_id in self._tasks
            )
            
            if all_predecessors_completed and successor_id in self._tasks:
                ready_tasks.append(self._tasks[successor_id])
        
        return ready_tasks

    def get_graph_edges(self) -> List[tuple]:
        return list(self._graph.edges())


class LangGraphWorkflow(BaseWorkflow):
    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id
        self._tasks: Dict[str, LangGraphTask] = {}
