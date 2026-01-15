"""
CLI for Lattice distributed task runner.
"""
import argparse
import asyncio
import sys
import logging

import uvicorn

from lattice.config.logging import setup_logging
from lattice.core.worker import Worker
from lattice.executor.sandbox import set_sandbox_config, SandboxConfig, SandboxLevel

logger = logging.getLogger(__name__)


async def start_head_async(
    port: int,
    ray_head_port: int,
    sandbox_level: str = "none",
    metrics_enabled: bool = True,
    metrics_exporter: str = "prometheus",
    metrics_endpoint: str = None,
) -> None:
    from lattice.api.server import create_app, get_orchestrator

    if sandbox_level != "none":
        config = SandboxConfig(level=SandboxLevel(sandbox_level))
        set_sandbox_config(config)
        logger.info(f"Sandbox enabled: {sandbox_level}")

    app = create_app(
        ray_head_port=ray_head_port,
        metrics_enabled=metrics_enabled,
        metrics_exporter=metrics_exporter,
        metrics_endpoint=metrics_endpoint,
    )
    orchestrator = get_orchestrator()

    if metrics_enabled:
        if metrics_exporter == "prometheus":
            logger.info("OpenTelemetry metrics enabled (Prometheus exporter at /metrics)")
        elif metrics_exporter in ("otlp", "otlp_http"):
            endpoint = metrics_endpoint or "default"
            logger.info(f"OpenTelemetry metrics enabled (OTLP exporter to {endpoint})")
        elif metrics_exporter == "console":
            logger.info("OpenTelemetry metrics enabled (Console exporter)")
        else:
            logger.info(f"OpenTelemetry metrics enabled ({metrics_exporter} exporter)")

    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)

    monitor_task = asyncio.create_task(orchestrator.start_monitor())

    try:
        await asyncio.gather(server.serve(), monitor_task)
    except asyncio.CancelledError:
        logger.info("Shutting down...")
        orchestrator.cleanup()


def start_head(
    port: int,
    ray_head_port: int,
    sandbox_level: str = "none",
    metrics_enabled: bool = True,
    metrics_exporter: str = "prometheus",
    metrics_endpoint: str = None,
) -> None:
    asyncio.run(start_head_async(
        port, ray_head_port, sandbox_level,
        metrics_enabled, metrics_exporter, metrics_endpoint
    ))


def start_worker(address: str) -> None:
    Worker.start(address)


def stop_worker() -> None:
    Worker.stop()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="lattice",
        description="Lattice distributed task runner",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("start", help="Start a Lattice node")
    start_group = start_parser.add_mutually_exclusive_group(required=True)
    start_group.add_argument("--head", action="store_true", help="Start as head node")
    start_group.add_argument("--worker", action="store_true", help="Start as worker node")

    start_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for head node (default: 8000)",
    )
    start_parser.add_argument(
        "--ray-head-port",
        type=int,
        default=6379,
        help="Port for Ray head (default: 6379)",
    )
    start_parser.add_argument(
        "--addr",
        help="Address of head node (required for worker)",
    )
    start_parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Log level (default: INFO)",
    )
    start_parser.add_argument(
        "--log-file",
        help="Log file path",
    )
    start_parser.add_argument(
        "--sandbox",
        default="none",
        choices=["none", "subprocess", "seccomp", "docker"],
        help="Sandbox isolation level for task execution (default: none)",
    )
    start_parser.add_argument(
        "--metrics",
        action="store_true",
        default=True,
        help="Enable metrics collection (default: enabled)",
    )
    start_parser.add_argument(
        "--no-metrics",
        action="store_true",
        help="Disable metrics collection",
    )
    start_parser.add_argument(
        "--metrics-exporter",
        default="prometheus",
        choices=["prometheus", "otlp", "otlp_http", "console"],
        help="Metrics exporter type (default: prometheus)",
    )
    start_parser.add_argument(
        "--metrics-endpoint",
        help="OTLP endpoint URL (e.g., http://localhost:4317 for gRPC, http://localhost:4318/v1/metrics for HTTP)",
    )

    stop_parser = subparsers.add_parser("stop", help="Stop Lattice worker")
    stop_parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )
    stop_parser.add_argument("--log-file", help="Log file path")

    args = parser.parse_args()

    setup_logging(args.log_level, getattr(args, "log_file", None))

    if args.command == "start":
        if args.head:
            metrics_enabled = not getattr(args, "no_metrics", False)
            start_head(
                args.port,
                args.ray_head_port,
                args.sandbox,
                metrics_enabled,
                getattr(args, "metrics_exporter", "prometheus"),
                getattr(args, "metrics_endpoint", None),
            )
        elif args.worker:
            if not args.addr:
                parser.error("--addr is required when using --worker")
            start_worker(args.addr)
    elif args.command == "stop":
        stop_worker()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
