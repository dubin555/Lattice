"""
Lattice Observability Module.

Provides OpenTelemetry-based metrics for monitoring Lattice workflows and tasks.
Supports multiple exporter backends (Prometheus, OTLP, Console).
"""

from lattice.observability.metrics import (
    # Initialization
    init_metrics,
    shutdown_metrics,
    is_initialized,
    get_meter_provider,
    get_meter,
    ExporterType,
    # Task metrics
    record_task_submitted,
    record_task_completed,
    record_task_failed,
    record_task_cancelled,
    update_queue_size,
    # Workflow metrics
    record_workflow_created,
    record_workflow_started,
    record_workflow_completed,
    record_workflow_failed,
    # API metrics
    record_api_request,
    # Resource metrics
    update_node_count,
    # Context managers
    TaskTimer,
    WorkflowTimer,
)

from lattice.observability.middleware import MetricsMiddleware

__all__ = [
    # Initialization
    "init_metrics",
    "shutdown_metrics",
    "is_initialized",
    "get_meter_provider",
    "get_meter",
    "ExporterType",
    # Task metrics
    "record_task_submitted",
    "record_task_completed",
    "record_task_failed",
    "record_task_cancelled",
    "update_queue_size",
    # Workflow metrics
    "record_workflow_created",
    "record_workflow_started",
    "record_workflow_completed",
    "record_workflow_failed",
    # API metrics
    "record_api_request",
    # Resource metrics
    "update_node_count",
    # Context managers
    "TaskTimer",
    "WorkflowTimer",
    # Middleware
    "MetricsMiddleware",
]
