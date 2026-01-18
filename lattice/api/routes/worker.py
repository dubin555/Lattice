"""
Worker API routes.
"""
from fastapi import APIRouter, HTTPException

from lattice.api.models.schemas import (
    StartWorkerRequest,
    StartWorkerResponse,
    GetRayPortResponse,
)
from lattice.api.dependencies import get_orchestrator
from lattice.api.exceptions import handle_route_exceptions

router = APIRouter(tags=["worker"])


@router.post("/start_worker", response_model=StartWorkerResponse)
@handle_route_exceptions
async def start_worker(request: StartWorkerRequest):
    orchestrator = get_orchestrator()
    orchestrator.add_worker(
        node_ip=request.node_ip,
        node_id=request.node_id,
        resources=request.resources,
    )
    return StartWorkerResponse(status="success")


@router.post("/get_head_ray_port", response_model=GetRayPortResponse)
@handle_route_exceptions
async def get_head_ray_port():
    orchestrator = get_orchestrator()
    port = orchestrator.ray_head_port
    return GetRayPortResponse(status="success", port=port)
