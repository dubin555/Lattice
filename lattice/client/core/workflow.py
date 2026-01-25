"""
Lattice workflow client for building and executing workflows.
"""
import json
import logging
import threading
from typing import Dict, List, Any, Optional, Callable, Union, TYPE_CHECKING

import websocket

from lattice.client.core.models import LatticeTask, TaskOutput
from lattice.client.core.decorator import get_task_metadata

if TYPE_CHECKING:
    from lattice.client.base import BaseClient

logger = logging.getLogger(__name__)


class LatticeWorkflow:
    """
    Workflow builder and executor.

    Uses a BaseClient instance for HTTP requests to ensure consistent
    error handling across all client operations.
    """

    def __init__(self, workflow_id: str, client: Union["BaseClient", str]):
        """
        Initialize the workflow.

        Args:
            workflow_id: The ID of the workflow.
            client: Either a BaseClient instance or a server URL string
                   (for backward compatibility).
        """
        self.workflow_id = workflow_id

        # Support both new (client instance) and old (server_url string) signatures
        if isinstance(client, str):
            # Backward compatibility: create a minimal client-like object
            from lattice.client.base import BaseClient
            self._client = BaseClient(client)
            self.server_url = client.rstrip("/")
        else:
            self._client = client
            self.server_url = client.server_url

        self._tasks: Dict[str, LatticeTask] = {}
        self._nodes: Dict[str, Dict[str, Any]] = {}
        self._edges: List[tuple] = []
        self._results_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._cache_lock = threading.Lock()

    def add_task(
        self,
        task_func: Optional[Callable] = None,
        inputs: Optional[Dict[str, Any]] = None,
        task_name: Optional[str] = None,
    ) -> LatticeTask:
        if task_func is None:
            raise ValueError("task_func is required")

        metadata = get_task_metadata(task_func)

        if task_name is None:
            task_name = metadata.func_name

        data = {
            "workflow_id": self.workflow_id,
            "task_type": "code",
            "task_name": task_name,
        }

        result = self._client._post("/add_task", data)
        if result.get("status") != "success":
            from lattice.exceptions import LatticeClientError
            raise LatticeClientError(
                f"Failed to add task: {result}",
                details={"response": result}
            )

        task_id = result["task_id"]

        task_input = self._build_task_input(inputs or {}, metadata)
        task_output = self._build_task_output(metadata)

        save_data = {
            "workflow_id": self.workflow_id,
            "task_id": task_id,
            "task_name": task_name,
            "code_str": metadata.code_str,
            "serialized_code": metadata.serialized_code,
            "task_input": task_input,
            "task_output": task_output,
            "resources": metadata.resources,
            "batch_config": metadata.batch_config.to_dict() if metadata.batch_config else None,
        }

        self._client._post("/save_task_and_add_edge", save_data)
        
        task = LatticeTask(
            task_id=task_id,
            workflow_id=self.workflow_id,
            server_url=self.server_url,
            task_name=task_name,
            output_keys=metadata.outputs,
        )
        self._tasks[task_id] = task
        
        self._nodes[task_id] = {
            "name": task_name,
            "func_name": metadata.func_name,
            "inputs": metadata.inputs,
            "outputs": metadata.outputs,
            "resources": metadata.resources,
        }
        
        if inputs:
            for input_value in inputs.values():
                if isinstance(input_value, TaskOutput):
                    source_task_id = input_value.task_id
                    if (source_task_id, task_id) not in self._edges:
                        self._edges.append((source_task_id, task_id))
        
        return task

    def _build_task_input(self, inputs: Dict[str, Any], metadata) -> Dict[str, Any]:
        task_input = {"input_params": {}}
        
        for idx, input_key in enumerate(metadata.inputs, start=1):
            input_value = inputs.get(input_key)
            
            if isinstance(input_value, TaskOutput):
                input_schema = "from_task"
                value = input_value.to_reference_string()
            else:
                input_schema = "from_user"
                value = input_value if input_value is not None else ""
            
            task_input["input_params"][str(idx)] = {
                "key": input_key,
                "input_schema": input_schema,
                "data_type": metadata.data_types.get(input_key, "str"),
                "value": value,
            }
        
        return task_input

    def _build_task_output(self, metadata) -> Dict[str, Any]:
        task_output = {"output_params": {}}
        
        for idx, output_key in enumerate(metadata.outputs, start=1):
            task_output["output_params"][str(idx)] = {
                "key": output_key,
                "data_type": metadata.data_types.get(output_key, "str"),
            }
        
        return task_output

    def add_edge(self, source_task: LatticeTask, target_task: LatticeTask) -> None:
        data = {
            "workflow_id": self.workflow_id,
            "source_task_id": source_task.task_id,
            "target_task_id": target_task.task_id,
        }

        self._client._post("/add_edge", data)

    def run(self) -> str:
        data = {"workflow_id": self.workflow_id}

        result = self._client._post("/run_workflow", data)
        if result.get("status") != "success":
            from lattice.exceptions import LatticeClientError
            raise LatticeClientError(
                f"Failed to run workflow: {result}",
                details={"response": result}
            )

        return result.get("run_id")

    def get_results(
        self,
        run_id: str,
        verbose: bool = True,
        timeout: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Get workflow execution results via WebSocket.

        Args:
            run_id: The workflow run ID.
            verbose: If True, print messages as they arrive.
            timeout: Maximum time to wait for results in seconds.
                    If None, waits indefinitely.

        Returns:
            List of result messages from the workflow execution.

        Raises:
            WorkflowTimeoutError: If timeout is exceeded.
            WebSocketError: If WebSocket connection fails.
        """
        # Check cache first (thread-safe)
        with self._cache_lock:
            if run_id in self._results_cache:
                cached = self._results_cache[run_id]
                if verbose:
                    for msg in cached:
                        print(msg)
                return cached

        ws_url = self.server_url.replace("http://", "ws://").replace("https://", "wss://")
        url = f"{ws_url}/get_workflow_res/{self.workflow_id}/{run_id}"

        messages: List[Dict[str, Any]] = []
        done_event = threading.Event()
        error_holder: List[Exception] = []

        def on_message(ws, message):
            try:
                msg_data = json.loads(message)
                messages.append(msg_data)
                if verbose:
                    print(msg_data)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse WebSocket message: {e}")

        def on_error(ws, error):
            error_holder.append(error)
            if verbose:
                print(f"WebSocket error: {error}")
            done_event.set()

        def on_close(ws, close_code, close_msg):
            done_event.set()

        def on_open(ws):
            pass

        ws = websocket.WebSocketApp(
            url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )

        ws_thread = threading.Thread(target=ws.run_forever)
        ws_thread.daemon = True
        ws_thread.start()

        # Wait for completion with optional timeout
        completed = done_event.wait(timeout=timeout)

        if not completed:
            # Timeout occurred - close WebSocket and raise error
            try:
                ws.close()
            except Exception:
                pass
            from lattice.exceptions import WorkflowTimeoutError
            raise WorkflowTimeoutError(run_id, timeout)

        # Check for WebSocket errors
        if error_holder:
            from lattice.exceptions import WebSocketError
            raise WebSocketError(str(error_holder[0]), {"run_id": run_id})

        # Cache results (thread-safe)
        with self._cache_lock:
            self._results_cache[run_id] = messages

        return messages

    def __repr__(self) -> str:
        return f"LatticeWorkflow(id='{self.workflow_id[:8]}...', tasks={len(self._tasks)})"
