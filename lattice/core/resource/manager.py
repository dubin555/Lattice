"""
Resource manager for distributed node management.
"""
import logging
import threading
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from lattice.core.resource.node import Node, NodeResources, GpuResource, NodeStatus, SelectedNode

logger = logging.getLogger(__name__)


@dataclass
class TaskResourceRequirements:
    cpu: float = 1.0
    memory_bytes: int = 0
    gpu: int = 0
    gpu_memory: int = 0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskResourceRequirements":
        return cls(
            cpu=data.get("cpu", 1.0),
            memory_bytes=data.get("cpu_mem", data.get("memory_bytes", 0)),
            gpu=data.get("gpu", 0),
            gpu_memory=data.get("gpu_mem", data.get("gpu_memory", 0)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cpu": self.cpu,
            "cpu_mem": self.memory_bytes,
            "gpu": self.gpu,
            "gpu_mem": self.gpu_memory,
        }


class ResourceManager:
    """Thread-safe resource manager for distributed node management."""

    def __init__(self):
        self._nodes: Dict[str, Node] = {}
        self._lock = threading.RLock()
        self._head_node_id: Optional[str] = None
        self._head_node_ip: Optional[str] = None
        self._last_log_time: float = 0
        self._log_interval: float = 3.0

    @property
    def head_node_id(self) -> Optional[str]:
        return self._head_node_id

    @property
    def head_node_ip(self) -> Optional[str]:
        return self._head_node_ip

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    def initialize_with_ray(self) -> None:
        import ray
        from lattice.utils.gpu import collect_gpu_info
        
        ray.init(address='auto', ignore_reinit_error=True)
        self._head_node_id = ray.get_runtime_context().get_node_id()
        self._head_node_ip = ray.util.get_node_ip_address()
        
        head_resources = self._collect_head_resources()
        self.add_node(
            node_id=self._head_node_id,
            node_ip=self._head_node_ip,
            resources=head_resources,
        )
        logger.info(f"Initialized head node: {self._head_node_id}")

    def initialize_local(self) -> None:
        import multiprocessing
        
        self._head_node_id = "local"
        self._head_node_ip = "127.0.0.1"
        
        resources = {
            "cpu": multiprocessing.cpu_count(),
            "cpu_mem": 0,
            "gpu_resource": {},
        }
        
        self.add_node(
            node_id=self._head_node_id,
            node_ip=self._head_node_ip,
            resources=resources,
        )
        logger.info("Initialized local executor")

    def _collect_head_resources(self) -> Dict[str, Any]:
        import ray
        from lattice.utils.gpu import collect_gpu_info
        
        head_node = None
        for node in ray.nodes():
            if node["NodeID"] == self._head_node_id:
                head_node = node
                break
        
        if head_node is None:
            raise RuntimeError("Head node not found in Ray cluster")

        resources = {
            "cpu": head_node["Resources"]["CPU"],
            "cpu_mem": head_node["Resources"]["memory"],
            "gpu_resource": {},
        }

        gpu_info = collect_gpu_info()
        for gpu in gpu_info:
            gpu_id = gpu["index"]
            resources["gpu_resource"][gpu_id] = {
                "gpu_id": gpu_id,
                "gpu_mem": gpu["memory_free"],
                "gpu_num": 1,
            }

        return resources

    def add_node(self, node_id: str, node_ip: str, resources: Dict[str, Any]) -> None:
        cpu_count = resources.get("cpu", 0)
        memory_bytes = resources.get("cpu_mem", 0)

        gpu_resources = {}
        for gpu_id, gpu_data in resources.get("gpu_resource", {}).items():
            gpu_id_int = int(gpu_id)
            gpu_mem = gpu_data["gpu_mem"]
            gpu_resources[gpu_id_int] = GpuResource(
                gpu_id=gpu_id_int,
                gpu_memory_total=gpu_mem,
                gpu_memory_available=gpu_mem,
                gpu_count=gpu_data.get("gpu_num", 1),
            )

        node_resources = NodeResources(
            cpu_count=cpu_count,
            memory_bytes=memory_bytes,
            gpu_resources=gpu_resources,
        )

        # Total resources is a copy with gpu_memory_available reset to total
        total_gpu_resources = {
            gpu_id: GpuResource(
                gpu_id=gpu.gpu_id,
                gpu_memory_total=gpu.gpu_memory_total,
                gpu_memory_available=gpu.gpu_memory_total,
                gpu_count=1,
            )
            for gpu_id, gpu in gpu_resources.items()
        }
        total_resources = NodeResources(
            cpu_count=cpu_count,
            memory_bytes=memory_bytes,
            gpu_resources=total_gpu_resources,
        )

        with self._lock:
            self._nodes[node_id] = Node(
                node_id=node_id,
                node_ip=node_ip,
                available_resources=node_resources,
                total_resources=total_resources,
                status=NodeStatus.ALIVE,
            )
        logger.info(f"Added node {node_id} at {node_ip}")

    def remove_node(self, node_id: str) -> None:
        with self._lock:
            if node_id in self._nodes:
                del self._nodes[node_id]
                logger.info(f"Removed node {node_id}")

    def get_node(self, node_id: str) -> Optional[Node]:
        with self._lock:
            return self._nodes.get(node_id)

    def select_node(self, requirements: TaskResourceRequirements) -> Optional[SelectedNode]:
        """Thread-safe node selection with atomic check-and-allocate."""
        with self._lock:
            for node_id, node in list(self._nodes.items()):
                if node.can_run_task(
                    cpu=requirements.cpu,
                    memory=requirements.memory_bytes,
                    gpu=requirements.gpu,
                    gpu_memory=requirements.gpu_memory,
                ):
                    try:
                        gpu_id = node.allocate_resources(
                            cpu=requirements.cpu,
                            memory=requirements.memory_bytes,
                            gpu=requirements.gpu,
                            gpu_memory=requirements.gpu_memory,
                        )
                        return SelectedNode(
                            node_id=node_id,
                            node_ip=node.node_ip,
                            gpu_id=gpu_id,
                        )
                    except ValueError:
                        # Allocation failed, try next node
                        continue

        logger.debug("No suitable node found for task requirements")
        return None

    def release_task_resources(
        self,
        node_id: str,
        requirements: TaskResourceRequirements,
        gpu_id: Optional[int] = None,
    ) -> None:
        with self._lock:
            node = self._nodes.get(node_id)
            if node is None:
                logger.warning(f"Cannot release resources: node {node_id} not found")
                return

            node.release_resources(
                cpu=requirements.cpu,
                memory=requirements.memory_bytes,
                gpu=requirements.gpu,
                gpu_memory=requirements.gpu_memory,
                gpu_id=gpu_id,
            )

    def check_node_health(self) -> List[str]:
        import ray

        dead_nodes = []
        ray_nodes = {n["NodeID"]: n for n in ray.nodes()}

        with self._lock:
            for node_id, node in list(self._nodes.items()):
                ray_node = ray_nodes.get(node_id)
                if ray_node is None or not ray_node.get("Alive", False):
                    node.status = NodeStatus.DEAD
                    dead_nodes.append(node_id)
                    del self._nodes[node_id]
                    logger.warning(f"Node {node_id} is dead, removed from pool")

        return dead_nodes

    def log_node_status(self) -> None:
        current_time = time.time()
        if current_time - self._last_log_time < self._log_interval:
            return

        self._last_log_time = current_time
        with self._lock:
            logger.debug(f"=== Node Status ({len(self._nodes)} nodes) ===")
            for node_id, node in self._nodes.items():
                logger.debug(
                    f"  Node {node_id[:8]}: CPU={node.available_resources.cpu_count:.1f}, "
                    f"Memory={node.available_resources.memory_bytes}, "
                    f"GPUs={len(node.available_resources.gpu_resources)}"
                )

    def get_cluster_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "node_count": len(self._nodes),
                "head_node_id": self._head_node_id,
                "head_node_ip": self._head_node_ip,
                "nodes": {
                    node_id: {
                        "node_ip": node.node_ip,
                        "status": node.status.value,
                        "available_cpu": node.available_resources.cpu_count,
                        "available_memory": node.available_resources.memory_bytes,
                        "gpu_count": len(node.available_resources.gpu_resources),
                }
                for node_id, node in self._nodes.items()
            },
        }
