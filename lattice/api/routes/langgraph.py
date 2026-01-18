"""
LangGraph API routes.
"""
import uuid
from fastapi import APIRouter, HTTPException

from lattice.api.models.schemas import (
    AddLangGraphTaskRequest,
    AddTaskResponse,
    RunLangGraphTaskRequest,
    RunLangGraphTaskResponse,
)
from lattice.core.workflow.base import LangGraphTask, LangGraphWorkflow
from lattice.api.dependencies import get_orchestrator
from lattice.api.exceptions import handle_route_exceptions

router = APIRouter(tags=["langgraph"])


@router.post("/add_langgraph_task", response_model=AddTaskResponse)
@handle_route_exceptions
async def add_langgraph_task(request: AddLangGraphTaskRequest):
    orchestrator = get_orchestrator()
    workflow = orchestrator.get_workflow(request.workflow_id)

    if workflow is None:
        workflow = LangGraphWorkflow(request.workflow_id)
        orchestrator._workflows[request.workflow_id] = workflow

    task_id = str(uuid.uuid4())
    # Support both "serialized_code" (new) and "code_ser" (legacy) fields
    serialized_code = request.serialized_code or request.code_ser
    task = LangGraphTask(
        workflow_id=request.workflow_id,
        task_id=task_id,
        task_name=request.task_name,
        serialized_code=serialized_code,
        resources=request.resources,
    )
    workflow.add_task(task_id, task)

    return AddTaskResponse(status="success", task_id=task_id)


@router.post("/run_langgraph_task", response_model=RunLangGraphTaskResponse)
@handle_route_exceptions
async def run_langgraph_task(request: RunLangGraphTaskRequest):
    orchestrator = get_orchestrator()
    result = await orchestrator.run_langgraph_task(
        workflow_id=request.workflow_id,
        task_id=request.task_id,
        serialized_args=request.args,
        serialized_kwargs=request.kwargs,
    )
    return RunLangGraphTaskResponse(status="success", result=result)
