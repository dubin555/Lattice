"""
Lattice workflow client for building and executing workflows.
"""
import json
import threading
from typing import Dict, List, Any, Optional, Callable

import requests
import websocket

from lattice.client.core.models import LatticeTask, TaskOutput
from lattice.client.core.decorator import get_task_metadata


class LatticeWorkflow:
    def __init__(self, workflow_id: str, server_url: str):
        self.workflow_id = workflow_id
        self.server_url = server_url.rstrip("/")
        self._tasks: Dict[str, LatticeTask] = {}
        self._nodes: Dict[str, Dict[str, Any]] = {}
        self._edges: List[tuple] = []
        self._results_cache: Dict[str, List[Dict[str, Any]]] = {}

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
        
        url = f"{self.server_url}/add_task"
        data = {
            "workflow_id": self.workflow_id,
            "task_type": "code",
            "task_name": task_name,
        }
        
        response = requests.post(url, json=data)
        if response.status_code != 200:
            raise Exception(f"Failed to add task: {response.text}")
        
        result = response.json()
        if result.get("status") != "success":
            raise Exception(f"Failed to add task: {result}")
        
        task_id = result["task_id"]
        
        task_input = self._build_task_input(inputs or {}, metadata)
        task_output = self._build_task_output(metadata)
        
        save_url = f"{self.server_url}/save_task_and_add_edge"
        save_data = {
            "workflow_id": self.workflow_id,
            "task_id": task_id,
            "code_str": metadata.code_str,
            "code_ser": metadata.serialized_code,
            "task_input": task_input,
            "task_output": task_output,
            "resources": metadata.resources,
        }
        
        save_response = requests.post(save_url, json=save_data)
        if save_response.status_code != 200:
            raise Exception(f"Failed to save task: {save_response.text}")
        
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
        url = f"{self.server_url}/add_edge"
        data = {
            "workflow_id": self.workflow_id,
            "source_task_id": source_task.task_id,
            "target_task_id": target_task.task_id,
        }
        
        response = requests.post(url, json=data)
        if response.status_code != 200:
            raise Exception(f"Failed to add edge: {response.text}")

    def run(self) -> str:
        url = f"{self.server_url}/run_workflow"
        data = {"workflow_id": self.workflow_id}
        
        response = requests.post(url, json=data)
        if response.status_code != 200:
            raise Exception(f"Failed to run workflow: {response.text}")
        
        result = response.json()
        if result.get("status") != "success":
            raise Exception(f"Failed to run workflow: {result}")
        
        return result.get("run_id")

    def get_results(self, run_id: str, verbose: bool = True) -> List[Dict[str, Any]]:
        if run_id in self._results_cache:
            cached = self._results_cache[run_id]
            if verbose:
                for msg in cached:
                    print(msg)
            return cached
        
        ws_url = self.server_url.replace("http://", "ws://").replace("https://", "wss://")
        url = f"{ws_url}/get_workflow_res/{self.workflow_id}/{run_id}"
        
        messages = []
        
        def on_message(ws, message):
            msg_data = json.loads(message)
            messages.append(msg_data)
            if verbose:
                print(msg_data)
        
        def on_error(ws, error):
            if verbose:
                print(f"WebSocket error: {error}")
        
        def on_close(ws, close_code, close_msg):
            pass
        
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
        
        import time
        last_count = 0
        while ws_thread.is_alive() or len(messages) > last_count:
            while len(messages) > last_count:
                last_count += 1
            time.sleep(0.1)
        
        self._results_cache[run_id] = messages
        return messages

    def __repr__(self) -> str:
        return f"LatticeWorkflow(id='{self.workflow_id[:8]}...', tasks={len(self._tasks)})"
