"""
LLM instance management for running LLM servers on Ray.
"""
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Any

import ray
import requests

logger = logging.getLogger(__name__)


@dataclass
class LLMInstanceInfo:
    instance_id: str
    model: str
    node_id: str
    node_ip: str
    port: int
    gpu_id: Optional[int]
    resources: Dict[str, Any]
    actor: Any = None


@ray.remote
class LLMServerActor:
    def __init__(self, model: str, gpu_id: Optional[int] = None, **kwargs):
        self.model = model
        self.gpu_id = str(gpu_id) if gpu_id is not None else None
        self.host = "0.0.0.0"
        self.port = self._find_free_port()
        self.extra_args = kwargs
        self.process = None
        self.ready = False

    def _find_free_port(self, start_port: int = 8000) -> int:
        import socket
        port = start_port
        while port <= 65535:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(("127.0.0.1", port))
                    return port
            except OSError:
                port += 1
        raise RuntimeError("No free port found")

    def get_port(self) -> int:
        return self.port

    def start_server(self, timeout: int = 120) -> bool:
        if self.ready:
            return True

        cmd = [
            "python", "-m", "vllm.entrypoints.openai.api_server",
            "--model", self.model,
            "--host", self.host,
            "--port", str(self.port),
        ]
        
        env = os.environ.copy()
        if self.gpu_id is not None:
            env["CUDA_VISIBLE_DEVICES"] = self.gpu_id

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

        health_url = f"http://127.0.0.1:{self.port}/health"
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                resp = requests.get(health_url, timeout=2)
                if resp.status_code == 200:
                    self.ready = True
                    logger.info(f"LLM server {self.model} ready on port {self.port}")
                    return True
            except requests.RequestException:
                pass
            time.sleep(1)

        self.process.terminate()
        self.process.wait()
        logger.error(f"LLM server {self.model} failed to start within {timeout}s")
        return False

    def stop_server(self, timeout: int = 5) -> None:
        if self.process is None:
            return
        
        self.process.terminate()
        try:
            self.process.wait(timeout=timeout)
            logger.info(f"LLM server {self.model} stopped")
        except subprocess.TimeoutExpired:
            logger.warning(f"Force killing LLM server {self.model}")
            self.process.kill()
            self.process.wait()


class LLMInstanceManager:
    def __init__(self):
        self._instances: Dict[str, LLMInstanceInfo] = {}

    def get_instance(self, instance_id: str) -> Optional[LLMInstanceInfo]:
        return self._instances.get(instance_id)

    def get_instance_address(self, instance_id: str) -> Optional[str]:
        instance = self._instances.get(instance_id)
        if instance is None:
            return None
        return f"{instance.node_ip}:{instance.port}"

    def start_instance(
        self,
        instance_id: str,
        model: str,
        node_id: str,
        node_ip: str,
        gpu_id: Optional[int],
        resources: Dict[str, Any],
    ) -> int:
        actor = LLMServerActor.options(
            scheduling_strategy=ray.util.scheduling_strategies.NodeAffinitySchedulingStrategy(
                node_id=node_id,
                soft=False,
            ),
        ).remote(model=model, gpu_id=gpu_id)
        
        ray.get(actor.start_server.remote())
        port = ray.get(actor.get_port.remote())
        
        self._instances[instance_id] = LLMInstanceInfo(
            instance_id=instance_id,
            model=model,
            node_id=node_id,
            node_ip=node_ip,
            port=port,
            gpu_id=gpu_id,
            resources=resources,
            actor=actor,
        )
        
        logger.info(f"Started LLM instance {instance_id} on {node_ip}:{port}")
        return port

    def stop_instance(self, instance_id: str) -> Optional[Dict[str, Any]]:
        instance = self._instances.get(instance_id)
        if instance is None:
            return None
        
        if instance.actor is not None:
            ray.get(instance.actor.stop_server.remote())
        
        resource_detail = {
            "node_id": instance.node_id,
            "gpu_id": instance.gpu_id,
            "resources": instance.resources,
        }
        
        del self._instances[instance_id]
        logger.info(f"Stopped LLM instance {instance_id}")
        
        return resource_detail

    def list_instances(self) -> Dict[str, Dict[str, Any]]:
        return {
            instance_id: {
                "model": info.model,
                "node_ip": info.node_ip,
                "port": info.port,
                "address": f"{info.node_ip}:{info.port}",
            }
            for instance_id, info in self._instances.items()
        }
