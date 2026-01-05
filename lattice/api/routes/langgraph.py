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

router = APIRouter(tags=["langgraph"])

_orchestrator = None


def set_orchestrator(orchestrator):
    global _orchestrator
    _orchestrator = orchestrator


def get_orchestrator():
    if _orchestrator is None:
        raise RuntimeError("Orchestrator not initialized")
    return _orchestrator


@router.post("/add_langgraph_task", response_model=AddTaskResponse)
async def add_langgraph_task(request: AddLangGraphTaskRequest):
    try:
        orchestrator = get_orchestrator()
        workflow = orchestrator.get_workflow(request.workflow_id)
        
        if workflow is None:
            workflow = LangGraphWorkflow(request.workflow_id)
            orchestrator._workflows[request.workflow_id] = workflow

        task_id = str(uuid.uuid4())
        task = LangGraphTask(
            workflow_id=request.workflow_id,
            task_id=task_id,
            task_name=request.task_name,
            serialized_code=request.code_ser,
            resources=request.resources,
        )
        workflow.add_task(task_id, task)

        return AddTaskResponse(status="success", task_id=task_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run_langgraph_task", response_model=RunLangGraphTaskResponse)
async def run_langgraph_task(request: RunLangGraphTaskRequest):
    try:
        orchestrator = get_orchestrator()
        result = await orchestrator.run_langgraph_task(
            workflow_id=request.workflow_id,
            task_id=request.task_id,
            serialized_args=request.args,
            serialized_kwargs=request.kwargs,
        )
        return RunLangGraphTaskResponse(status="success", result=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
