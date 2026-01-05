"""
Worker node implementation for connecting to Lattice head node.
"""
import logging
import subprocess
from typing import Dict, Any

import ray
import requests

from lattice.utils.gpu import collect_gpu_info

logger = logging.getLogger(__name__)


class Worker:
    @staticmethod
    def _post(url: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        response = requests.post(url, json=data or {})
        if response.status_code != 200:
            raise Exception(f"Request failed: {response.status_code}, {response.text}")
        return response.json()

    @staticmethod
    def start(head_address: str) -> None:
        try:
            head_url = f"http://{head_address}"
            data = Worker._post(f"{head_url}/get_head_ray_port")
            ray_port = data["port"]
            
            ray_address = f"{head_address.split(':')[0]}:{ray_port}"
            command = ["ray", "start", "--address", ray_address]
            
            result = subprocess.run(command, check=True, text=True, capture_output=True)
            if result.returncode != 0:
                raise RuntimeError(f"Failed to start Ray worker: {result.stderr}")
            
            node_id = ray.get_runtime_context().get_node_id()
            node_ip = None
            
            while True:
                for node in ray.nodes():
                    if node["NodeID"] == node_id and node["Alive"]:
                        node_ip = node["NodeManagerAddress"]
                        break
                if node_ip:
                    break
            
            resources = {
                "cpu": node["Resources"]["CPU"],
                "cpu_mem": node["Resources"]["memory"],
                "gpu_resource": {},
            }
            
            gpu_info = collect_gpu_info()
            for gpu in gpu_info:
                resources["gpu_resource"][gpu["index"]] = {
                    "gpu_id": gpu["index"],
                    "gpu_mem": gpu["memory_free"],
                    "gpu_num": 1,
                }
            
            Worker._post(
                f"{head_url}/start_worker",
                {
                    "node_ip": node_ip,
                    "node_id": node_id,
                    "resources": resources,
                },
            )
            
            logger.info(f"Worker started successfully: {node_id}")
            print("=== Worker started successfully ===")
            
        except Exception as e:
            logger.error(f"Failed to start worker: {e}")
            raise

    @staticmethod
    def stop() -> None:
        try:
            result = subprocess.run(
                ["ray", "stop"],
                check=True,
                text=True,
                capture_output=True,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Failed to stop Ray: {result.stderr}")
            
            logger.info("Worker stopped successfully")
            print("=== Worker stopped successfully ===")
            
        except Exception as e:
            logger.error(f"Failed to stop worker: {e}")
            raise
