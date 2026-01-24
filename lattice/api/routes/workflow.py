"""
Workflow API routes.
"""
import uuid
from fastapi import APIRouter, HTTPException, WebSocket, Request

from lattice.api.models.schemas import (
    CreateWorkflowResponse,
    AddTaskRequest,
    AddTaskResponse,
    SaveTaskRequest,
    SaveTaskResponse,
    AddEdgeRequest,
    AddEdgeResponse,
    RunWorkflowRequest,
    RunWorkflowResponse,
    GetTasksResponse,
)
from lattice.core.workflow.base import CodeTask, TaskType
from lattice.exceptions import WorkflowNotFoundError, TaskNotFoundError
from lattice.api.dependencies import get_orchestrator
from lattice.api.exceptions import handle_route_exceptions
from lattice.utils.compat import get_serialized_code

router = APIRouter(tags=["workflow"])


@router.post("/create_workflow", response_model=CreateWorkflowResponse)
@handle_route_exceptions
async def create_workflow():
    workflow_id = str(uuid.uuid4())
    get_orchestrator().create_workflow(workflow_id)
    return CreateWorkflowResponse(status="success", workflow_id=workflow_id)


@router.post("/add_task", response_model=AddTaskResponse)
@handle_route_exceptions
async def add_task(request: AddTaskRequest):
    orchestrator = get_orchestrator()
    workflow = orchestrator.get_workflow(request.workflow_id)
    if workflow is None:
        raise WorkflowNotFoundError(request.workflow_id)

    task_id = str(uuid.uuid4())

    if request.task_type == TaskType.CODE.value:
        task = CodeTask(
            workflow_id=request.workflow_id,
            task_id=task_id,
            task_name=request.task_name,
        )
        workflow.add_task(task_id, task)
    else:
        raise HTTPException(status_code=400, detail=f"Invalid task type: {request.task_type}")

    return AddTaskResponse(status="success", task_id=task_id)


@router.post("/save_task", response_model=SaveTaskResponse)
@handle_route_exceptions
async def save_task(request: SaveTaskRequest):
    orchestrator = get_orchestrator()
    workflow = orchestrator.get_workflow(request.workflow_id)
    if workflow is None:
        raise WorkflowNotFoundError(request.workflow_id)

    task = workflow.get_task(request.task_id)
    if task is None:
        raise TaskNotFoundError(request.task_id, request.workflow_id)

    # Support both "serialized_code" (new) and "code_ser" (legacy) fields
    serialized_code = request.serialized_code or request.code_ser
    if not request.code_str and not serialized_code:
        raise HTTPException(status_code=400, detail="Either code_str or serialized_code is required")

    task.save(
        task_input=request.task_input,
        task_output=request.task_output,
        code_str=request.code_str,
        serialized_code=serialized_code,
        resources=request.resources,
    )

    return SaveTaskResponse(status="success")


@router.post("/save_task_and_add_edge", response_model=SaveTaskResponse)
@handle_route_exceptions
async def save_task_and_add_edge(request: Request):
    data = await request.json()
    orchestrator = get_orchestrator()
    workflow = orchestrator.get_workflow(data["workflow_id"])
    if workflow is None:
        raise WorkflowNotFoundError(data["workflow_id"])

    task = workflow.get_task(data["task_id"])
    if task is None:
        raise TaskNotFoundError(data["task_id"], data["workflow_id"])

    code_str = data.get("code_str")
    serialized_code = get_serialized_code(data)
    if not code_str and not serialized_code:
        raise HTTPException(status_code=400, detail="Either code_str or serialized_code is required")

    task.save(
        task_input=data["task_input"],
        task_output=data["task_output"],
        code_str=code_str,
        serialized_code=serialized_code,
        resources=data["resources"],
        batch_config=data.get("batch_config"),
    )

    input_params = data["task_input"].get("input_params", {})
    for _, input_param in input_params.items():
        if input_param.get("input_schema") == "from_task":
            source_task_id = input_param["value"].split(".")[0]
            workflow.add_edge(source_task_id, data["task_id"])

    return SaveTaskResponse(status="success")


@router.post("/add_edge", response_model=AddEdgeResponse)
@handle_route_exceptions
async def add_edge(request: AddEdgeRequest):
    orchestrator = get_orchestrator()
    workflow = orchestrator.get_workflow(request.workflow_id)
    if workflow is None:
        raise WorkflowNotFoundError(request.workflow_id)

    workflow.add_edge(request.source_task_id, request.target_task_id)
    return AddEdgeResponse(status="success")


@router.post("/del_edge", response_model=AddEdgeResponse)
@handle_route_exceptions
async def del_edge(request: AddEdgeRequest):
    orchestrator = get_orchestrator()
    workflow = orchestrator.get_workflow(request.workflow_id)
    if workflow is None:
        raise WorkflowNotFoundError(request.workflow_id)

    workflow.remove_edge(request.source_task_id, request.target_task_id)
    return AddEdgeResponse(status="success")


@router.post("/del_task")
@handle_route_exceptions
async def del_task(request: Request):
    data = await request.json()
    orchestrator = get_orchestrator()
    workflow = orchestrator.get_workflow(data["workflow_id"])
    if workflow is None:
        raise WorkflowNotFoundError(data["workflow_id"])

    workflow.remove_task(data["task_id"])
    return {"status": "success", "task_id": data["task_id"]}


@router.get("/get_workflow_tasks/{workflow_id}", response_model=GetTasksResponse)
@handle_route_exceptions
async def get_workflow_tasks(workflow_id: str):
    orchestrator = get_orchestrator()
    tasks = orchestrator.get_workflow_tasks(workflow_id)
    return GetTasksResponse(status="success", tasks=tasks)


@router.post("/run_workflow", response_model=RunWorkflowResponse)
@handle_route_exceptions
async def run_workflow(request: RunWorkflowRequest):
    orchestrator = get_orchestrator()
    run_id = orchestrator.run_workflow(request.workflow_id)
    return RunWorkflowResponse(status="success", run_id=run_id)


@router.websocket("/get_workflow_res/{workflow_id}/{run_id}")
async def get_workflow_results(websocket: WebSocket, workflow_id: str, run_id: str):
    orchestrator = get_orchestrator()
    try:
        await websocket.accept()

        results = await orchestrator.wait_workflow_complete(run_id)

        for msg in results:
            await websocket.send_json(msg)

        await websocket.send_json({
            "type": "finish_workflow",
            "data": {"run_id": run_id},
        })

        await websocket.close()
    except Exception:
        await orchestrator.stop_workflow(run_id)
        await websocket.close()
