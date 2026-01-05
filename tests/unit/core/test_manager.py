"""
Unit tests for resource/manager module (ResourceManager).
"""
import pytest
from unittest.mock import MagicMock, patch
from lattice.core.resource.manager import ResourceManager, TaskResourceRequirements
from lattice.core.resource.node import Node, NodeResources, GpuResource, NodeStatus, SelectedNode


class TestResourceManager:
    def test_creation(self):
        manager = ResourceManager()
        assert manager.node_count == 0
        assert manager.head_node_id is None
        assert manager.head_node_ip is None

    def test_add_node_basic(self):
        manager = ResourceManager()
        manager.add_node(
            node_id="node-1",
            node_ip="192.168.1.1",
            resources={"cpu": 8, "cpu_mem": 16000},
        )
        
        assert manager.node_count == 1
        node = manager.get_node("node-1")
        assert node is not None
        assert node.node_ip == "192.168.1.1"

    def test_add_node_with_gpu(self):
        manager = ResourceManager()
        manager.add_node(
            node_id="node-1",
            node_ip="192.168.1.1",
            resources={
                "cpu": 8,
                "cpu_mem": 16000,
                "gpu_resource": {
                    0: {"gpu_id": 0, "gpu_mem": 8000, "gpu_num": 1},
                    1: {"gpu_id": 1, "gpu_mem": 8000, "gpu_num": 1},
                },
            },
        )
        
        node = manager.get_node("node-1")
        assert len(node.available_resources.gpu_resources) == 2

    def test_remove_node(self):
        manager = ResourceManager()
        manager.add_node("node-1", "192.168.1.1", {"cpu": 4})
        
        manager.remove_node("node-1")
        
        assert manager.node_count == 0
        assert manager.get_node("node-1") is None

    def test_remove_nonexistent_node(self):
        manager = ResourceManager()
        manager.remove_node("nonexistent")
        assert manager.node_count == 0

    def test_select_node_cpu_only(self):
        manager = ResourceManager()
        manager.add_node("node-1", "192.168.1.1", {"cpu": 8, "cpu_mem": 16000})
        
        requirements = TaskResourceRequirements(cpu=2, memory_bytes=1000)
        selected = manager.select_node(requirements)
        
        assert selected is not None
        assert selected.node_id == "node-1"
        assert selected.node_ip == "192.168.1.1"
        assert selected.gpu_id is None

    def test_select_node_insufficient_resources(self):
        manager = ResourceManager()
        manager.add_node("node-1", "192.168.1.1", {"cpu": 2, "cpu_mem": 1000})
        
        requirements = TaskResourceRequirements(cpu=10, memory_bytes=2000)
        selected = manager.select_node(requirements)
        
        assert selected is None

    def test_select_node_with_gpu(self):
        manager = ResourceManager()
        manager.add_node(
            "node-1",
            "192.168.1.1",
            {
                "cpu": 8,
                "cpu_mem": 16000,
                "gpu_resource": {
                    0: {"gpu_id": 0, "gpu_mem": 8000, "gpu_num": 1},
                },
            },
        )
        
        requirements = TaskResourceRequirements(cpu=2, gpu=1, gpu_memory=4000)
        selected = manager.select_node(requirements)
        
        assert selected is not None
        assert selected.gpu_id == 0

    def test_release_task_resources(self):
        manager = ResourceManager()
        manager.add_node("node-1", "192.168.1.1", {"cpu": 8, "cpu_mem": 16000})
        
        requirements = TaskResourceRequirements(cpu=4, memory_bytes=8000)
        manager.select_node(requirements)
        
        node = manager.get_node("node-1")
        assert node.available_resources.cpu_count == 4.0
        
        manager.release_task_resources("node-1", requirements)
        
        assert node.available_resources.cpu_count == 8.0

    def test_release_nonexistent_node_resources(self):
        manager = ResourceManager()
        requirements = TaskResourceRequirements(cpu=2)
        manager.release_task_resources("nonexistent", requirements)

    def test_get_cluster_status(self):
        manager = ResourceManager()
        manager.add_node("node-1", "192.168.1.1", {"cpu": 8, "cpu_mem": 16000})
        manager.add_node("node-2", "192.168.1.2", {"cpu": 4, "cpu_mem": 8000})
        
        status = manager.get_cluster_status()
        
        assert status["node_count"] == 2
        assert "node-1" in status["nodes"]
        assert "node-2" in status["nodes"]
        assert status["nodes"]["node-1"]["node_ip"] == "192.168.1.1"
        assert status["nodes"]["node-2"]["available_cpu"] == 4.0

    def test_multiple_node_selection(self):
        manager = ResourceManager()
        manager.add_node("node-1", "192.168.1.1", {"cpu": 4, "cpu_mem": 8000})
        manager.add_node("node-2", "192.168.1.2", {"cpu": 8, "cpu_mem": 16000})
        
        req1 = TaskResourceRequirements(cpu=3, memory_bytes=4000)
        selected1 = manager.select_node(req1)
        
        req2 = TaskResourceRequirements(cpu=2, memory_bytes=2000)
        selected2 = manager.select_node(req2)
        
        assert selected1 is not None
        assert selected2 is not None
        assert {selected1.node_id, selected2.node_id} == {"node-1", "node-2"}


class TestTaskResourceRequirementsExtended:
    def test_from_dict_with_alternative_keys(self):
        data = {"cpu": 2, "memory_bytes": 4000, "gpu": 1, "gpu_memory": 2000}
        req = TaskResourceRequirements.from_dict(data)
        
        assert req.cpu == 2
        assert req.memory_bytes == 4000
        assert req.gpu == 1
        assert req.gpu_memory == 2000

    def test_from_dict_prefers_cpu_mem(self):
        data = {"cpu_mem": 5000, "memory_bytes": 3000}
        req = TaskResourceRequirements.from_dict(data)
        
        assert req.memory_bytes == 5000
