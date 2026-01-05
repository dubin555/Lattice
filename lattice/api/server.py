"""
FastAPI server for Lattice.
"""
import signal
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from lattice.core.orchestrator import Orchestrator
from lattice.api.routes import workflow, langgraph, worker


class OrchestratorManager:
    _instance: Optional[Orchestrator] = None
    _ray_head_port: int = 6379

    @classmethod
    def initialize(cls, ray_head_port: int = 6379) -> Orchestrator:
        if cls._instance is None:
            cls._ray_head_port = ray_head_port
            cls._instance = Orchestrator(ray_head_port=ray_head_port)
            cls._instance.initialize()
        return cls._instance

    @classmethod
    def get(cls) -> Orchestrator:
        if cls._instance is None:
            raise RuntimeError("Orchestrator not initialized")
        return cls._instance

    @classmethod
    def cleanup(cls) -> None:
        if cls._instance is not None:
            cls._instance.cleanup()
            cls._instance = None


def get_orchestrator() -> Orchestrator:
    return OrchestratorManager.get()


@asynccontextmanager
async def lifespan(app: FastAPI):
    orchestrator = OrchestratorManager.get()
    await orchestrator.start_monitor()
    yield
    OrchestratorManager.cleanup()


app = FastAPI(
    title="Lattice API",
    description="Task-level distributed framework for LLM agents",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def create_app(ray_head_port: int = 6379) -> FastAPI:
    OrchestratorManager.initialize(ray_head_port)
    orchestrator = OrchestratorManager.get()
    
    workflow.set_orchestrator(orchestrator)
    langgraph.set_orchestrator(orchestrator)
    worker.set_orchestrator(orchestrator)
    
    app.include_router(workflow.router)
    app.include_router(langgraph.router)
    app.include_router(worker.router)
    
    def signal_handler(signum, frame):
        OrchestratorManager.cleanup()
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    return app


async def startup_event():
    try:
        orchestrator = OrchestratorManager.get()
        await orchestrator.start_monitor()
    except RuntimeError:
        pass


async def shutdown_event():
    OrchestratorManager.cleanup()


app.add_event_handler("startup", startup_event)
app.add_event_handler("shutdown", shutdown_event)
