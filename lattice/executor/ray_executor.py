"""
Ray-based executor backend for distributed task execution.
"""
import logging
import os
import subprocess
from typing import Any, Dict, List, Optional

import ray

from lattice.executor.base import (
    ExecutorBackend,
    ExecutorType,
    TaskSubmission,
    TaskHandle,
    TaskError,
    TaskCancelledError,
    NodeFailedError,
)

logger = logging.getLogger(__name__)


@ray.remote(max_retries=0)
def _execute_task(func, args, kwargs, cuda_visible_devices: Optional[str] = None):
    if cuda_visible_devices:
        os.environ["CUDA_VISIBLE_DEVICES"] = cuda_visible_devices
    return func(*args, **kwargs)


class RayExecutor(ExecutorBackend):
    def __init__(self, ray_head_port: int = 6379, start_ray: bool = True):
        self._ray_head_port = ray_head_port
        self._start_ray = start_ray
        self._initialized = False

    def initialize(self) -> None:
        if self._initialized:
            return

        if self._start_ray:
            self._launch_ray_head()

        if not ray.is_initialized():
            ray.init(address="auto", ignore_reinit_error=True)

        self._initialized = True
        logger.info("RayExecutor initialized")

    def _launch_ray_head(self) -> None:
        try:
            result = subprocess.run(
                ["ray", "start", "--head", "--port", str(self._ray_head_port)],
                check=True, text=True, capture_output=True,
            )
            if result.returncode != 0:
                raise RuntimeError(result.stderr)
            logger.info(f"Ray head started on port {self._ray_head_port}")
        except Exception as e:
            logger.error(f"Failed to launch Ray head: {e}")
            raise

    def submit(self, submission: TaskSubmission) -> TaskHandle:
        resources = submission.resources or {}
        num_cpus = resources.get("cpu", 1)
        num_gpus = resources.get("gpu", 0)
        memory = resources.get("cpu_mem", 0)

        options = {"num_cpus": num_cpus}
        if memory > 0:
            options["memory"] = memory
        if num_gpus > 0:
            options["num_gpus"] = num_gpus
        if submission.node_id:
            options["scheduling_strategy"] = ray.util.scheduling_strategies.NodeAffinitySchedulingStrategy(
                node_id=submission.node_id,
                soft=False,
            )

        cuda_devices = str(submission.gpu_id) if submission.gpu_id is not None else None

        ref = _execute_task.options(**options).remote(
            submission.func,
            submission.args,
            submission.kwargs,
            cuda_devices,
        )
        return TaskHandle(handle_id=ref, executor_type=ExecutorType.RAY)

    def get_result(self, handle: TaskHandle) -> Any:
        try:
            return ray.get(handle.handle_id)
        except ray.exceptions.RayTaskError as e:
            raise TaskError(str(e)) from e
        except ray.exceptions.TaskCancelledError as e:
            raise TaskCancelledError(str(e)) from e
        except (ray.exceptions.NodeDiedError, ray.exceptions.ObjectLostError) as e:
            raise NodeFailedError(str(e)) from e

    def wait(self, handles: List[TaskHandle], timeout: float = 0) -> tuple[List[TaskHandle], List[TaskHandle]]:
        if not handles:
            return [], []

        refs = [h.handle_id for h in handles]
        ref_to_handle = {h.handle_id: h for h in handles}

        try:
            done_refs, pending_refs = ray.wait(refs, num_returns=len(refs), timeout=timeout if timeout > 0 else None)
        except Exception:
            return [], handles

        done = [ref_to_handle[r] for r in done_refs]
        pending = [ref_to_handle[r] for r in pending_refs]
        return done, pending

    def cancel(self, handle: TaskHandle) -> bool:
        try:
            ray.cancel(handle.handle_id, force=True)
            return True
        except Exception:
            return False

    def shutdown(self) -> None:
        try:
            subprocess.run(["ray", "stop"], check=True, text=True, capture_output=True)
        except Exception as e:
            logger.warning(f"Failed to stop Ray: {e}")

    def get_available_resources(self) -> Dict[str, Any]:
        if not ray.is_initialized():
            return {}

        resources = {"nodes": []}
        for node in ray.nodes():
            if node["Alive"]:
                resources["nodes"].append({
                    "node_id": node["NodeID"],
                    "node_ip": node["NodeManagerAddress"],
                    "cpu": node["Resources"].get("CPU", 0),
                    "memory": node["Resources"].get("memory", 0),
                    "gpu": node["Resources"].get("GPU", 0),
                })
        return resources
