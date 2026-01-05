"""
Node resource representation for distributed task scheduling.
"""
from dataclasses import dataclass, field
from typing import Dict, Optional, Any
from enum import Enum


class NodeStatus(Enum):
    ALIVE = "alive"
    DEAD = "dead"
    UNKNOWN = "unknown"


@dataclass
class GpuResource:
    gpu_id: int
    gpu_memory_total: int
    gpu_memory_available: int
    gpu_count: int = 1

    def has_sufficient_memory(self, required_memory: int) -> bool:
        return self.gpu_memory_available >= required_memory

    def has_available_gpu(self) -> bool:
        return self.gpu_count >= 1

    def allocate(self, memory: int, count: int = 1) -> None:
        if memory > self.gpu_memory_available:
            raise ValueError(f"Insufficient GPU memory: {self.gpu_memory_available} < {memory}")
        if count > self.gpu_count:
            raise ValueError(f"Insufficient GPU count: {self.gpu_count} < {count}")
        self.gpu_memory_available -= memory
        self.gpu_count -= count

    def release(self, memory: int, count: int = 1) -> None:
        self.gpu_memory_available += memory
        self.gpu_count += count


@dataclass
class NodeResources:
    cpu_count: float
    memory_bytes: int
    gpu_resources: Dict[int, GpuResource] = field(default_factory=dict)

    def has_sufficient_cpu(self, required_cpu: float) -> bool:
        return self.cpu_count >= required_cpu

    def has_sufficient_memory(self, required_memory: int) -> bool:
        return self.memory_bytes >= required_memory

    def get_available_gpu(self, required_memory: int = 0) -> Optional[int]:
        for gpu_id, gpu in self.gpu_resources.items():
            if gpu.has_available_gpu() and gpu.has_sufficient_memory(required_memory):
                return gpu_id
        return None

    def allocate_cpu(self, cpu: float) -> None:
        if cpu > self.cpu_count:
            raise ValueError(f"Insufficient CPU: {self.cpu_count} < {cpu}")
        self.cpu_count -= cpu

    def allocate_memory(self, memory: int) -> None:
        if memory > self.memory_bytes:
            raise ValueError(f"Insufficient memory: {self.memory_bytes} < {memory}")
        self.memory_bytes -= memory

    def release_cpu(self, cpu: float) -> None:
        self.cpu_count += cpu

    def release_memory(self, memory: int) -> None:
        self.memory_bytes += memory


@dataclass
class Node:
    node_id: str
    node_ip: str
    available_resources: NodeResources
    total_resources: NodeResources
    status: NodeStatus = NodeStatus.ALIVE

    def is_alive(self) -> bool:
        return self.status == NodeStatus.ALIVE

    def can_run_task(self, cpu: float, memory: int, gpu: int = 0, gpu_memory: int = 0) -> bool:
        if not self.is_alive():
            return False
        if not self.available_resources.has_sufficient_cpu(cpu):
            return False
        if not self.available_resources.has_sufficient_memory(memory):
            return False
        if gpu > 0:
            gpu_id = self.available_resources.get_available_gpu(gpu_memory)
            if gpu_id is None:
                return False
        return True

    def allocate_resources(self, cpu: float, memory: int, gpu: int = 0, gpu_memory: int = 0) -> Optional[int]:
        self.available_resources.allocate_cpu(cpu)
        self.available_resources.allocate_memory(memory)
        
        gpu_id = None
        if gpu > 0:
            gpu_id = self.available_resources.get_available_gpu(gpu_memory)
            if gpu_id is not None:
                self.available_resources.gpu_resources[gpu_id].allocate(gpu_memory, gpu)
        
        return gpu_id

    def release_resources(self, cpu: float, memory: int, gpu: int = 0, gpu_memory: int = 0, gpu_id: Optional[int] = None) -> None:
        self.available_resources.release_cpu(cpu)
        self.available_resources.release_memory(memory)
        
        if gpu > 0 and gpu_id is not None:
            self.available_resources.gpu_resources[gpu_id].release(gpu_memory, gpu)


@dataclass
class SelectedNode:
    node_id: str
    node_ip: str
    gpu_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_ip": self.node_ip,
            "gpu_id": self.gpu_id,
        }
