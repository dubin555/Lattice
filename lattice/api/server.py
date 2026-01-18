"""
FastAPI server for Lattice.
"""
import signal
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Depends, Response
from fastapi.middleware.cors import CORSMiddleware

from lattice.core.orchestrator import Orchestrator
from lattice.api.routes import workflow, langgraph, worker
from lattice.api.dependencies import set_orchestrator

# Import metrics - optional dependency
try:
    from lattice.observability import (
        init_metrics,
        shutdown_metrics,
        is_initialized,
        MetricsMiddleware,
        ExporterType,
    )
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False


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
    if METRICS_AVAILABLE:
        shutdown_metrics()


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


def create_app(
    ray_head_port: int = 6379,
    metrics_enabled: bool = True,
    metrics_exporter: str = "prometheus",
    metrics_endpoint: Optional[str] = None,
) -> FastAPI:
    """
    Create and configure the Lattice FastAPI application.

    Args:
        ray_head_port: Port for Ray head node
        metrics_enabled: Whether to enable metrics collection
        metrics_exporter: Metrics exporter type ("prometheus", "otlp", "otlp_http", "console")
        metrics_endpoint: OTLP endpoint URL (required for otlp/otlp_http exporters)

    Returns:
        Configured FastAPI application
    """
    OrchestratorManager.initialize(ray_head_port)
    orchestrator = OrchestratorManager.get()

    set_orchestrator(orchestrator)

    app.include_router(workflow.router)
    app.include_router(langgraph.router)
    app.include_router(worker.router)

    # Add metrics middleware and endpoint if enabled
    if metrics_enabled and METRICS_AVAILABLE:
        # Initialize OpenTelemetry metrics
        exporter_kwargs = {}
        if metrics_endpoint and metrics_exporter in ("otlp", "otlp_http"):
            exporter_kwargs["endpoint"] = metrics_endpoint

        init_metrics(
            service_name="lattice",
            exporter_type=metrics_exporter,
            **exporter_kwargs,
        )

        app.add_middleware(MetricsMiddleware)

        # Add /metrics endpoint for Prometheus scraping
        if metrics_exporter == "prometheus":
            @app.get("/metrics", include_in_schema=False)
            async def metrics():
                """Expose Prometheus metrics via OpenTelemetry."""
                from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
                return Response(
                    content=generate_latest(),
                    media_type=CONTENT_TYPE_LATEST,
                )

    def signal_handler(signum, frame):
        OrchestratorManager.cleanup()
        if METRICS_AVAILABLE:
            shutdown_metrics()

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
    if METRICS_AVAILABLE:
        shutdown_metrics()


app.add_event_handler("startup", startup_event)
app.add_event_handler("shutdown", shutdown_event)
