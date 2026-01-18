"""
Local executor backend using concurrent.futures.
For development and testing without Ray.
"""
import logging
import os
import uuid
from concurrent.futures import ProcessPoolExecutor, Future, wait, FIRST_COMPLETED
from typing import Any, Dict, List, Optional

from lattice.executor.base import (
    ExecutorBackend,
    ExecutorType,
    TaskSubmission,
    TaskHandle,
    TaskError,
    TaskCancelledError,
)

logger = logging.getLogger(__name__)


def _execute_task(func, args, kwargs, gpu_id: Optional[int] = None):
    if gpu_id is not None:
        os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    return func(*args, **kwargs)


class LocalExecutor(ExecutorBackend):
    def __init__(self, max_workers: Optional[int] = None):
        self._max_workers = max_workers
        self._executor: Optional[ProcessPoolExecutor] = None
        self._futures: Dict[str, Future] = {}

    def initialize(self) -> None:
        if self._executor is not None:
            return
        self._executor = ProcessPoolExecutor(max_workers=self._max_workers)
        logger.info(f"LocalExecutor initialized with max_workers={self._max_workers}")

    def submit(self, submission: TaskSubmission) -> TaskHandle:
        if self._executor is None:
            self.initialize()

        handle_id = str(uuid.uuid4())
        future = self._executor.submit(
            _execute_task,
            submission.func,
            submission.args,
            submission.kwargs,
            submission.gpu_id,
        )
        self._futures[handle_id] = future
        return TaskHandle(handle_id=handle_id, executor_type=ExecutorType.LOCAL)

    def get_result(self, handle: TaskHandle) -> Any:
        future = self._futures.get(handle.handle_id)
        if future is None:
            raise TaskError(f"Unknown handle: {handle.handle_id}")

        try:
            result = future.result()
            del self._futures[handle.handle_id]
            return result
        except Exception as e:
            del self._futures[handle.handle_id]
            if future.cancelled():
                raise TaskCancelledError(str(e)) from e
            raise TaskError(str(e)) from e

    def wait(self, handles: List[TaskHandle], timeout: float = 0) -> tuple[List[TaskHandle], List[TaskHandle]]:
        if not handles:
            return [], []

        futures_map = {}
        for h in handles:
            f = self._futures.get(h.handle_id)
            if f:
                futures_map[f] = h

        if not futures_map:
            return [], handles

        done_futures, pending_futures = wait(
            list(futures_map.keys()),
            timeout=timeout if timeout > 0 else None,
            return_when=FIRST_COMPLETED if timeout == 0 else None,
        )

        done = [futures_map[f] for f in done_futures]
        pending = [futures_map[f] for f in pending_futures]
        return done, pending

    def cancel(self, handle: TaskHandle) -> bool:
        future = self._futures.get(handle.handle_id)
        if future is None:
            return False
        cancelled = future.cancel()
        if cancelled:
            del self._futures[handle.handle_id]
        return cancelled

    def shutdown(self) -> None:
        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None
            self._futures.clear()
            logger.info("LocalExecutor shutdown")

    def get_available_resources(self) -> Dict[str, Any]:
        import multiprocessing
        return {
            "nodes": [{
                "node_id": "local",
                "node_ip": "127.0.0.1",
                "cpu": multiprocessing.cpu_count(),
                "memory": 0,
                "gpu": 0,
            }]
        }
