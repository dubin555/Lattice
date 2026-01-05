"""
Workflow runtime management for distributed task execution.
"""
import logging
from typing import Dict, List, Optional, Any, Union

from lattice.core.runtime.task import (
    BaseTaskRuntime,
    CodeTaskRuntime,
    LangGraphTaskRuntime,
    TaskStatus,
)
from lattice.core.resource.node import SelectedNode

logger = logging.getLogger(__name__)


class WorkflowRuntime:
    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id
        self._tasks: Dict[str, BaseTaskRuntime] = {}
        self._ref_to_task_id: Dict[Any, str] = {}

    @property
    def task_count(self) -> int:
        return len(self._tasks)

    def add_task(self, task: BaseTaskRuntime) -> None:
        if task.task_id not in self._tasks:
            self._tasks[task.task_id] = task

    def get_task(self, task_id: str) -> Optional[BaseTaskRuntime]:
        return self._tasks.get(task_id)

    def get_task_by_ref(self, object_ref: Any) -> Optional[BaseTaskRuntime]:
        task_id = self._ref_to_task_id.get(object_ref)
        if task_id is None:
            return None
        return self._tasks.get(task_id)

    def set_task_running(
        self,
        task_id: str,
        object_ref: Any,
        selected_node: SelectedNode,
    ) -> None:
        task = self._tasks.get(task_id)
        if task is None:
            return
        
        task.set_running(object_ref, selected_node)
        self._ref_to_task_id[object_ref] = task_id

    def set_task_result(self, task: BaseTaskRuntime, result: Any) -> None:
        if task.task_id in self._tasks:
            self._tasks[task.task_id].set_completed(result)

    def get_running_task_refs(self) -> List[Any]:
        refs = []
        for task in self._tasks.values():
            if task.is_running() and task.object_ref is not None:
                refs.append(task.object_ref)
        return refs

    def get_running_tasks(self) -> List[BaseTaskRuntime]:
        return [task for task in self._tasks.values() if task.is_running()]

    def get_task_result(self, key: str) -> Optional[Any]:
        parts = key.split(".")
        if len(parts) < 3:
            return None
        
        task_id = parts[0]
        output_key = parts[2]
        
        task = self._tasks.get(task_id)
        if task is None or task.result is None:
            return None
        
        return task.result.get(output_key)


class WorkflowRuntimeManager:
    def __init__(self):
        self._workflows: Dict[str, WorkflowRuntime] = {}
        self._ref_to_workflow_id: Dict[Any, str] = {}
        self._task_to_workflow: Dict[str, str] = {}

    @property
    def workflow_count(self) -> int:
        return len(self._workflows)

    def get_or_create_workflow(self, workflow_id: str) -> WorkflowRuntime:
        if workflow_id not in self._workflows:
            self._workflows[workflow_id] = WorkflowRuntime(workflow_id)
        return self._workflows[workflow_id]

    def get_workflow(self, workflow_id: str) -> Optional[WorkflowRuntime]:
        return self._workflows.get(workflow_id)

    def get_workflow_by_task_id(self, task_id: str) -> Optional[WorkflowRuntime]:
        workflow_id = self._task_to_workflow.get(task_id)
        if workflow_id is None:
            return None
        return self._workflows.get(workflow_id)

    def add_task(self, task: BaseTaskRuntime) -> None:
        workflow = self.get_or_create_workflow(task.workflow_id)
        workflow.add_task(task)
        self._task_to_workflow[task.task_id] = task.workflow_id

    def run_task(
        self,
        task: BaseTaskRuntime,
        object_ref: Any,
        selected_node: SelectedNode,
    ) -> None:
        workflow = self._workflows.get(task.workflow_id)
        if workflow is None:
            return
        
        workflow.set_task_running(task.task_id, object_ref, selected_node)
        self._ref_to_workflow_id[object_ref] = task.workflow_id

    def get_task_by_ref(self, object_ref: Any) -> Optional[BaseTaskRuntime]:
        workflow_id = self._ref_to_workflow_id.get(object_ref)
        if workflow_id is None:
            return None
        
        workflow = self._workflows.get(workflow_id)
        if workflow is None:
            return None
        
        return workflow.get_task_by_ref(object_ref)

    def set_task_result(self, task: BaseTaskRuntime, result: Any) -> None:
        workflow = self._workflows.get(task.workflow_id)
        if workflow is not None:
            workflow.set_task_result(task, result)

    def get_running_task_refs(self) -> List[Any]:
        refs = []
        for workflow in self._workflows.values():
            refs.extend(workflow.get_running_task_refs())
        return refs

    def cancel_workflow(self, workflow_id: str) -> List[BaseTaskRuntime]:
        import ray
        
        workflow = self._workflows.get(workflow_id)
        if workflow is None:
            return []
        
        running_tasks = workflow.get_running_tasks()
        for task in running_tasks:
            if task.object_ref is not None:
                try:
                    ray.cancel(task.object_ref, force=True)
                except Exception as e:
                    logger.warning(f"Failed to cancel task {task.task_id}: {e}")
        
        self.clear_workflow(workflow_id)
        return running_tasks

    def clear_workflow(self, workflow_id: str) -> None:
        workflow = self._workflows.get(workflow_id)
        if workflow is None:
            return
        
        refs_to_delete = [
            ref for ref, wf_id in self._ref_to_workflow_id.items()
            if wf_id == workflow_id
        ]
        for ref in refs_to_delete:
            del self._ref_to_workflow_id[ref]
        
        tasks_to_delete = [
            task_id for task_id, wf_id in self._task_to_workflow.items()
            if wf_id == workflow_id
        ]
        for task_id in tasks_to_delete:
            del self._task_to_workflow[task_id]
        
        del self._workflows[workflow_id]
        logger.debug(f"Cleared workflow {workflow_id}")

    def get_task_result_value(self, workflow_id: str, key: str) -> Optional[Any]:
        workflow = self._workflows.get(workflow_id)
        if workflow is None:
            return None
        return workflow.get_task_result(key)
