"""
OpenTelemetry metrics definitions for Lattice.

This module provides metrics instrumentation using OpenTelemetry SDK,
with configurable exporter backends (Prometheus, OTLP, Console, etc.).
"""

import time
from typing import Optional, Callable, List
from enum import Enum


class ExporterType(str, Enum):
    """Supported metrics exporter types."""
    PROMETHEUS = "prometheus"
    OTLP = "otlp"
    OTLP_HTTP = "otlp_http"
    CONSOLE = "console"
    NONE = "none"  # For testing or disabled metrics


# Global state
_meter = None
_meter_provider = None
_initialized = False

# Metric instruments
_task_counter = None
_task_duration = None
_task_queue_size = None
_task_in_progress = None

_workflow_counter = None
_workflow_duration = None
_workflow_in_progress = None

_api_request_counter = None
_api_request_duration = None

_node_count = None

# State for observable gauges
_current_queue_size: int = 0
_current_node_count: int = 0


def _queue_size_callback(options):
    """Callback for queue size observable gauge."""
    from opentelemetry.metrics import Observation
    yield Observation(_current_queue_size)


def _node_count_callback(options):
    """Callback for node count observable gauge."""
    from opentelemetry.metrics import Observation
    yield Observation(_current_node_count)


def _create_exporter(
    exporter_type: ExporterType,
    **kwargs,
):
    """
    Create a metric reader based on the exporter type.

    Args:
        exporter_type: Type of exporter to create
        **kwargs: Additional arguments for the exporter
            - endpoint: OTLP endpoint URL
            - headers: OTLP headers dict
            - export_interval_millis: Export interval for periodic exporters

    Returns:
        A metric reader instance
    """
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

    export_interval = kwargs.pop("export_interval_millis", 10000)

    if exporter_type == ExporterType.PROMETHEUS:
        from opentelemetry.exporter.prometheus import PrometheusMetricReader
        return PrometheusMetricReader()

    elif exporter_type == ExporterType.OTLP:
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
        exporter = OTLPMetricExporter(**kwargs)
        return PeriodicExportingMetricReader(
            exporter,
            export_interval_millis=export_interval,
        )

    elif exporter_type == ExporterType.OTLP_HTTP:
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
        exporter = OTLPMetricExporter(**kwargs)
        return PeriodicExportingMetricReader(
            exporter,
            export_interval_millis=export_interval,
        )

    elif exporter_type == ExporterType.CONSOLE:
        from opentelemetry.sdk.metrics.export import ConsoleMetricExporter
        exporter = ConsoleMetricExporter()
        return PeriodicExportingMetricReader(
            exporter,
            export_interval_millis=export_interval,
        )

    elif exporter_type == ExporterType.NONE:
        return None

    else:
        raise ValueError(f"Unknown exporter type: {exporter_type}")


def init_metrics(
    service_name: str = "lattice",
    exporter_type: str | ExporterType = ExporterType.PROMETHEUS,
    additional_exporters: Optional[List[tuple]] = None,
    **exporter_kwargs,
):
    """
    Initialize OpenTelemetry metrics with the specified exporter(s).

    Args:
        service_name: Name of the service for resource identification
        exporter_type: Primary exporter type ("prometheus", "otlp", "otlp_http", "console", "none")
        additional_exporters: List of (exporter_type, kwargs) tuples for additional exporters
        **exporter_kwargs: Additional arguments for the primary exporter
            - endpoint: OTLP endpoint URL (e.g., "http://localhost:4317")
            - headers: OTLP headers dict
            - export_interval_millis: Export interval for periodic exporters

    Returns:
        The configured MeterProvider

    Example:
        # Prometheus only (default)
        init_metrics()

        # OTLP gRPC
        init_metrics(exporter_type="otlp", endpoint="http://localhost:4317")

        # OTLP HTTP
        init_metrics(exporter_type="otlp_http", endpoint="http://localhost:4318/v1/metrics")

        # Multiple exporters (Prometheus + OTLP)
        init_metrics(
            exporter_type="prometheus",
            additional_exporters=[
                ("otlp", {"endpoint": "http://localhost:4317"})
            ]
        )
    """
    global _meter, _meter_provider, _initialized
    global _task_counter, _task_duration, _task_queue_size, _task_in_progress
    global _workflow_counter, _workflow_duration, _workflow_in_progress
    global _api_request_counter, _api_request_duration
    global _node_count

    if _initialized:
        return _meter_provider

    from opentelemetry import metrics
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME

    # Convert string to enum if needed
    if isinstance(exporter_type, str):
        exporter_type = ExporterType(exporter_type)

    # Create resource
    resource = Resource.create({SERVICE_NAME: service_name})

    # Create metric readers
    readers = []

    # Primary exporter
    primary_reader = _create_exporter(exporter_type, **exporter_kwargs)
    if primary_reader is not None:
        readers.append(primary_reader)

    # Additional exporters
    if additional_exporters:
        for exp_type, exp_kwargs in additional_exporters:
            if isinstance(exp_type, str):
                exp_type = ExporterType(exp_type)
            reader = _create_exporter(exp_type, **exp_kwargs)
            if reader is not None:
                readers.append(reader)

    # Create and set meter provider
    _meter_provider = MeterProvider(resource=resource, metric_readers=readers)
    metrics.set_meter_provider(_meter_provider)

    # Get meter
    _meter = metrics.get_meter("lattice.metrics", version="2.0.0")

    # Create task metrics
    _task_counter = _meter.create_counter(
        name="lattice_task_total",
        description="Total number of tasks by status",
        unit="1",
    )

    _task_duration = _meter.create_histogram(
        name="lattice_task_duration_seconds",
        description="Task execution duration in seconds",
        unit="s",
    )

    _task_queue_size = _meter.create_observable_gauge(
        name="lattice_task_queue_size",
        description="Number of pending tasks in the scheduler queue",
        unit="1",
        callbacks=[_queue_size_callback],
    )

    _task_in_progress = _meter.create_up_down_counter(
        name="lattice_task_in_progress",
        description="Number of currently running tasks",
        unit="1",
    )

    # Create workflow metrics
    _workflow_counter = _meter.create_counter(
        name="lattice_workflow_total",
        description="Total number of workflows by status",
        unit="1",
    )

    _workflow_duration = _meter.create_histogram(
        name="lattice_workflow_duration_seconds",
        description="Workflow execution duration in seconds",
        unit="s",
    )

    _workflow_in_progress = _meter.create_up_down_counter(
        name="lattice_workflow_in_progress",
        description="Number of currently running workflows",
        unit="1",
    )

    # Create API metrics
    _api_request_counter = _meter.create_counter(
        name="lattice_api_request_total",
        description="Total number of API requests",
        unit="1",
    )

    _api_request_duration = _meter.create_histogram(
        name="lattice_api_request_duration_seconds",
        description="API request duration in seconds",
        unit="s",
    )

    # Create resource metrics
    _node_count = _meter.create_observable_gauge(
        name="lattice_node_count",
        description="Total number of registered nodes",
        unit="1",
        callbacks=[_node_count_callback],
    )

    _initialized = True
    return _meter_provider


def shutdown_metrics() -> None:
    """Shutdown the meter provider and flush metrics."""
    global _meter_provider, _initialized
    if _meter_provider is not None:
        _meter_provider.shutdown()
        _meter_provider = None
        _initialized = False


def is_initialized() -> bool:
    """Check if metrics have been initialized."""
    return _initialized


def get_meter_provider():
    """Get the current meter provider."""
    return _meter_provider


def get_meter():
    """Get the current meter instance."""
    return _meter


# =============================================================================
# Task Metrics Helper Functions
# =============================================================================


def record_task_submitted(workflow_id: str) -> None:
    """Record a task submission."""
    if _task_counter is not None:
        _task_counter.add(1, {"workflow_id": workflow_id, "status": "submitted"})
    if _task_in_progress is not None:
        _task_in_progress.add(1)


def record_task_completed(workflow_id: str, duration: float) -> None:
    """Record a task completion."""
    if _task_counter is not None:
        _task_counter.add(1, {"workflow_id": workflow_id, "status": "completed"})
    if _task_duration is not None:
        _task_duration.record(duration, {"workflow_id": workflow_id})
    if _task_in_progress is not None:
        _task_in_progress.add(-1)


def record_task_failed(workflow_id: str, duration: Optional[float] = None) -> None:
    """Record a task failure."""
    if _task_counter is not None:
        _task_counter.add(1, {"workflow_id": workflow_id, "status": "failed"})
    if duration is not None and _task_duration is not None:
        _task_duration.record(duration, {"workflow_id": workflow_id})
    if _task_in_progress is not None:
        _task_in_progress.add(-1)


def record_task_cancelled(workflow_id: str) -> None:
    """Record a task cancellation."""
    if _task_counter is not None:
        _task_counter.add(1, {"workflow_id": workflow_id, "status": "cancelled"})
    if _task_in_progress is not None:
        _task_in_progress.add(-1)


def update_queue_size(size: int) -> None:
    """Update the task queue size."""
    global _current_queue_size
    _current_queue_size = size


# =============================================================================
# Workflow Metrics Helper Functions
# =============================================================================


def record_workflow_created() -> None:
    """Record a workflow creation."""
    if _workflow_counter is not None:
        _workflow_counter.add(1, {"status": "created"})


def record_workflow_started() -> None:
    """Record a workflow start."""
    if _workflow_counter is not None:
        _workflow_counter.add(1, {"status": "running"})
    if _workflow_in_progress is not None:
        _workflow_in_progress.add(1)


def record_workflow_completed(duration: float) -> None:
    """Record a workflow completion."""
    if _workflow_counter is not None:
        _workflow_counter.add(1, {"status": "completed"})
    if _workflow_duration is not None:
        _workflow_duration.record(duration)
    if _workflow_in_progress is not None:
        _workflow_in_progress.add(-1)


def record_workflow_failed(duration: Optional[float] = None) -> None:
    """Record a workflow failure."""
    if _workflow_counter is not None:
        _workflow_counter.add(1, {"status": "failed"})
    if duration is not None and _workflow_duration is not None:
        _workflow_duration.record(duration)
    if _workflow_in_progress is not None:
        _workflow_in_progress.add(-1)


# =============================================================================
# API Metrics Helper Functions
# =============================================================================


def record_api_request(method: str, endpoint: str, status_code: int, duration: float) -> None:
    """Record an API request."""
    attributes = {
        "method": method,
        "endpoint": endpoint,
        "status_code": str(status_code),
    }
    if _api_request_counter is not None:
        _api_request_counter.add(1, attributes)
    if _api_request_duration is not None:
        _api_request_duration.record(duration, {"method": method, "endpoint": endpoint})


# =============================================================================
# Resource Metrics Helper Functions
# =============================================================================


def update_node_count(count: int) -> None:
    """Update the total node count."""
    global _current_node_count
    _current_node_count = count


# =============================================================================
# Context Managers
# =============================================================================


class TaskTimer:
    """Context manager for timing task execution."""

    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id
        self.start_time: Optional[float] = None

    def __enter__(self) -> "TaskTimer":
        self.start_time = time.time()
        record_task_submitted(self.workflow_id)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.start_time is None:
            return
        duration = time.time() - self.start_time
        if exc_type is not None:
            record_task_failed(self.workflow_id, duration)
        else:
            record_task_completed(self.workflow_id, duration)


class WorkflowTimer:
    """Context manager for timing workflow execution."""

    def __init__(self):
        self.start_time: Optional[float] = None

    def __enter__(self) -> "WorkflowTimer":
        self.start_time = time.time()
        record_workflow_started()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.start_time is None:
            return
        duration = time.time() - self.start_time
        if exc_type is not None:
            record_workflow_failed(duration)
        else:
            record_workflow_completed(duration)
