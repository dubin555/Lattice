"""
Pydantic models for API requests and responses.
"""
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional


class CreateWorkflowResponse(BaseModel):
    status: str
    workflow_id: str


class AddTaskRequest(BaseModel):
    workflow_id: str
    task_type: str = "code"
    task_name: str


class AddTaskResponse(BaseModel):
    status: str
    task_id: str


class SaveTaskRequest(BaseModel):
    workflow_id: str
    task_id: str
    task_input: Dict[str, Any]
    task_output: Dict[str, Any]
    resources: Dict[str, Any]
    code_str: Optional[str] = None
    code_ser: Optional[str] = None


class SaveTaskResponse(BaseModel):
    status: str


class AddEdgeRequest(BaseModel):
    workflow_id: str
    source_task_id: str
    target_task_id: str


class AddEdgeResponse(BaseModel):
    status: str


class RunWorkflowRequest(BaseModel):
    workflow_id: str


class RunWorkflowResponse(BaseModel):
    status: str
    run_id: str


class GetTasksResponse(BaseModel):
    status: str
    tasks: List[Dict[str, str]]


class AddLangGraphTaskRequest(BaseModel):
    workflow_id: str
    task_type: str = "langgraph"
    task_name: str
    code_ser: str
    resources: Dict[str, Any]


class RunLangGraphTaskRequest(BaseModel):
    workflow_id: str
    task_id: str
    args: str
    kwargs: str


class RunLangGraphTaskResponse(BaseModel):
    status: str
    result: Any


class StartWorkerRequest(BaseModel):
    node_ip: str
    node_id: str
    resources: Dict[str, Any]


class StartWorkerResponse(BaseModel):
    status: str


class GetRayPortResponse(BaseModel):
    status: str
    port: int


class StartLLMInstanceRequest(BaseModel):
    model: str
    cpu_nums: int = 1
    gpu_nums: int = 0
    memory: int = 0
    gpu_mem: int = 0


class StartLLMInstanceResponse(BaseModel):
    status: str
    host: str
    port: int
    instance_id: str


class StopLLMInstanceRequest(BaseModel):
    instance_id: str


class StopLLMInstanceResponse(BaseModel):
    status: str


class ErrorResponse(BaseModel):
    detail: str
