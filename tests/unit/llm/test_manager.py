"""
Unit tests for llm/manager module.

Note: Tests that require Ray are skipped. Only non-Ray functionality is tested.
"""
import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass
from typing import Dict, Optional, Any

pytest.importorskip("ray")

from lattice.llm.manager import LLMInstanceInfo, LLMInstanceManager


class TestLLMInstanceInfo:
    def test_creation(self):
        info = LLMInstanceInfo(
            instance_id="inst-1",
            model="gpt-4",
            node_id="node-1",
            node_ip="192.168.1.1",
            port=8080,
            gpu_id=0,
            resources={"cpu": 2, "gpu": 1},
        )
        
        assert info.instance_id == "inst-1"
        assert info.model == "gpt-4"
        assert info.node_id == "node-1"
        assert info.node_ip == "192.168.1.1"
        assert info.port == 8080
        assert info.gpu_id == 0
        assert info.resources == {"cpu": 2, "gpu": 1}
        assert info.actor is None

    def test_creation_without_gpu(self):
        info = LLMInstanceInfo(
            instance_id="inst-2",
            model="llama",
            node_id="node-1",
            node_ip="192.168.1.1",
            port=8081,
            gpu_id=None,
            resources={"cpu": 4},
        )
        
        assert info.gpu_id is None

    def test_with_actor(self):
        mock_actor = MagicMock()
        info = LLMInstanceInfo(
            instance_id="inst-3",
            model="model",
            node_id="node-1",
            node_ip="192.168.1.1",
            port=8082,
            gpu_id=None,
            resources={},
            actor=mock_actor,
        )
        
        assert info.actor == mock_actor


class TestLLMInstanceManager:
    def test_creation(self):
        manager = LLMInstanceManager()
        assert manager.list_instances() == {}

    def test_get_instance_nonexistent(self):
        manager = LLMInstanceManager()
        assert manager.get_instance("nonexistent") is None

    def test_get_instance_address_nonexistent(self):
        manager = LLMInstanceManager()
        assert manager.get_instance_address("nonexistent") is None

    def test_list_instances_empty(self):
        manager = LLMInstanceManager()
        assert manager.list_instances() == {}

    def test_stop_instance_nonexistent(self):
        manager = LLMInstanceManager()
        result = manager.stop_instance("nonexistent")
        assert result is None

    def test_internal_instance_storage(self):
        manager = LLMInstanceManager()
        
        info = LLMInstanceInfo(
            instance_id="inst-1",
            model="test-model",
            node_id="node-1",
            node_ip="192.168.1.1",
            port=8000,
            gpu_id=0,
            resources={"cpu": 1, "gpu": 1},
        )
        manager._instances["inst-1"] = info
        
        assert manager.get_instance("inst-1") == info
        assert manager.get_instance_address("inst-1") == "192.168.1.1:8000"

    def test_list_instances_with_data(self):
        manager = LLMInstanceManager()
        
        manager._instances["inst-1"] = LLMInstanceInfo(
            instance_id="inst-1",
            model="model-a",
            node_id="node-1",
            node_ip="192.168.1.1",
            port=8000,
            gpu_id=0,
            resources={},
        )
        manager._instances["inst-2"] = LLMInstanceInfo(
            instance_id="inst-2",
            model="model-b",
            node_id="node-2",
            node_ip="192.168.1.2",
            port=8001,
            gpu_id=None,
            resources={},
        )
        
        result = manager.list_instances()
        
        assert len(result) == 2
        assert result["inst-1"]["model"] == "model-a"
        assert result["inst-1"]["address"] == "192.168.1.1:8000"
        assert result["inst-2"]["model"] == "model-b"
        assert result["inst-2"]["port"] == 8001

    def test_stop_instance_returns_resource_detail(self):
        manager = LLMInstanceManager()
        
        manager._instances["inst-1"] = LLMInstanceInfo(
            instance_id="inst-1",
            model="model",
            node_id="node-1",
            node_ip="192.168.1.1",
            port=8000,
            gpu_id=0,
            resources={"cpu": 2, "gpu": 1, "gpu_mem": 4000},
            actor=None,
        )
        
        result = manager.stop_instance("inst-1")
        
        assert result is not None
        assert result["node_id"] == "node-1"
        assert result["gpu_id"] == 0
        assert result["resources"] == {"cpu": 2, "gpu": 1, "gpu_mem": 4000}
        
        assert manager.get_instance("inst-1") is None
