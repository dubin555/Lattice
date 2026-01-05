"""
Worker API routes.
"""
from fastapi import APIRouter, HTTPException

from lattice.api.models.schemas import (
    StartWorkerRequest,
    StartWorkerResponse,
    GetRayPortResponse,
)

router = APIRouter(tags=["worker"])

_orchestrator = None


def set_orchestrator(orchestrator):
    global _orchestrator
    _orchestrator = orchestrator


def get_orchestrator():
    if _orchestrator is None:
        raise RuntimeError("Orchestrator not initialized")
    return _orchestrator


@router.post("/start_worker", response_model=StartWorkerResponse)
async def start_worker(request: StartWorkerRequest):
    try:
        orchestrator = get_orchestrator()
        orchestrator.add_worker(
            node_ip=request.node_ip,
            node_id=request.node_id,
            resources=request.resources,
        )
        return StartWorkerResponse(status="success")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/get_head_ray_port", response_model=GetRayPortResponse)
async def get_head_ray_port():
    try:
        orchestrator = get_orchestrator()
        port = orchestrator.ray_head_port
        return GetRayPortResponse(status="success", port=port)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
