"""
Unit tests for core/resource module.
"""
import pytest
from lattice.core.resource.node import (
    Node,
    NodeResources,
    NodeStatus,
    GpuResource,
    SelectedNode,
)
from lattice.core.resource.manager import (
    ResourceManager,
    TaskResourceRequirements,
)


class TestGpuResource:
    def test_creation(self):
        gpu = GpuResource(gpu_id=0, gpu_memory_total=8000, gpu_memory_available=8000)
        assert gpu.gpu_id == 0
        assert gpu.gpu_memory_total == 8000
        assert gpu.gpu_memory_available == 8000
        assert gpu.gpu_count == 1

    def test_has_sufficient_memory(self):
        gpu = GpuResource(gpu_id=0, gpu_memory_total=8000, gpu_memory_available=4000)
        assert gpu.has_sufficient_memory(3000)
        assert gpu.has_sufficient_memory(4000)
        assert not gpu.has_sufficient_memory(5000)

    def test_allocate_release(self):
        gpu = GpuResource(gpu_id=0, gpu_memory_total=8000, gpu_memory_available=8000)
        gpu.allocate(memory=2000, count=1)
        assert gpu.gpu_memory_available == 6000
        assert gpu.gpu_count == 0
        
        gpu.release(memory=2000, count=1)
        assert gpu.gpu_memory_available == 8000
        assert gpu.gpu_count == 1

    def test_allocate_insufficient_memory_raises(self):
        gpu = GpuResource(gpu_id=0, gpu_memory_total=8000, gpu_memory_available=1000)
        with pytest.raises(ValueError, match="Insufficient GPU memory"):
            gpu.allocate(memory=2000)


class TestNodeResources:
    def test_creation(self):
        resources = NodeResources(cpu_count=8.0, memory_bytes=16000)
        assert resources.cpu_count == 8.0
        assert resources.memory_bytes == 16000
        assert len(resources.gpu_resources) == 0

    def test_has_sufficient_cpu(self):
        resources = NodeResources(cpu_count=4.0, memory_bytes=8000)
        assert resources.has_sufficient_cpu(2.0)
        assert resources.has_sufficient_cpu(4.0)
        assert not resources.has_sufficient_cpu(5.0)

    def test_has_sufficient_memory(self):
        resources = NodeResources(cpu_count=4.0, memory_bytes=8000)
        assert resources.has_sufficient_memory(4000)
        assert resources.has_sufficient_memory(8000)
        assert not resources.has_sufficient_memory(10000)

    def test_get_available_gpu(self):
        gpu = GpuResource(gpu_id=0, gpu_memory_total=8000, gpu_memory_available=4000)
        resources = NodeResources(cpu_count=4.0, memory_bytes=8000, gpu_resources={0: gpu})
        
        assert resources.get_available_gpu(required_memory=3000) == 0
        assert resources.get_available_gpu(required_memory=5000) is None

    def test_allocate_release_cpu_memory(self):
        resources = NodeResources(cpu_count=8.0, memory_bytes=16000)
        resources.allocate_cpu(2.0)
        resources.allocate_memory(4000)
        
        assert resources.cpu_count == 6.0
        assert resources.memory_bytes == 12000
        
        resources.release_cpu(2.0)
        resources.release_memory(4000)
        
        assert resources.cpu_count == 8.0
        assert resources.memory_bytes == 16000


class TestNode:
    def test_creation(self):
        resources = NodeResources(cpu_count=8.0, memory_bytes=16000)
        node = Node(
            node_id="node-1",
            node_ip="192.168.1.1",
            available_resources=resources,
            total_resources=resources,
        )
        assert node.node_id == "node-1"
        assert node.node_ip == "192.168.1.1"
        assert node.is_alive()

    def test_can_run_task(self):
        resources = NodeResources(cpu_count=8.0, memory_bytes=16000)
        node = Node(
            node_id="node-1",
            node_ip="192.168.1.1",
            available_resources=resources,
            total_resources=resources,
        )
        
        assert node.can_run_task(cpu=2.0, memory=4000)
        assert node.can_run_task(cpu=8.0, memory=16000)
        assert not node.can_run_task(cpu=10.0, memory=4000)
        assert not node.can_run_task(cpu=2.0, memory=20000)

    def test_dead_node_cannot_run_task(self):
        resources = NodeResources(cpu_count=8.0, memory_bytes=16000)
        node = Node(
            node_id="node-1",
            node_ip="192.168.1.1",
            available_resources=resources,
            total_resources=resources,
            status=NodeStatus.DEAD,
        )
        assert not node.can_run_task(cpu=1.0, memory=1000)


class TestSelectedNode:
    def test_creation(self):
        selected = SelectedNode(node_id="node-1", node_ip="192.168.1.1", gpu_id=0)
        assert selected.node_id == "node-1"
        assert selected.node_ip == "192.168.1.1"
        assert selected.gpu_id == 0

    def test_to_dict(self):
        selected = SelectedNode(node_id="node-1", node_ip="192.168.1.1", gpu_id=0)
        result = selected.to_dict()
        assert result == {
            "node_id": "node-1",
            "node_ip": "192.168.1.1",
            "gpu_id": 0,
        }


class TestTaskResourceRequirements:
    def test_from_dict(self):
        data = {"cpu": 2, "cpu_mem": 4000, "gpu": 1, "gpu_mem": 2000}
        req = TaskResourceRequirements.from_dict(data)
        assert req.cpu == 2
        assert req.memory_bytes == 4000
        assert req.gpu == 1
        assert req.gpu_memory == 2000

    def test_from_dict_with_defaults(self):
        req = TaskResourceRequirements.from_dict({})
        assert req.cpu == 1.0
        assert req.memory_bytes == 0
        assert req.gpu == 0
        assert req.gpu_memory == 0

    def test_to_dict(self):
        req = TaskResourceRequirements(cpu=2.0, memory_bytes=4000, gpu=1, gpu_memory=2000)
        result = req.to_dict()
        assert result == {"cpu": 2.0, "cpu_mem": 4000, "gpu": 1, "gpu_mem": 2000}
