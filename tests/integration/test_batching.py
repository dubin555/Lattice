"""
Integration tests for batching functionality.

These tests require a running Lattice server.
"""
import pytest
import requests
import time
from typing import List, Dict, Any

from lattice.client.core.client import LatticeClient
from lattice.client.core.decorator import task


SERVER_URL = "http://localhost:8000"


def server_is_running():
    try:
        response = requests.get(f"{SERVER_URL}/docs", timeout=2)
        return response.status_code == 200
    except requests.RequestException:
        return False


@pytest.fixture(scope="module")
def check_server():
    if not server_is_running():
        pytest.skip("Lattice server not running at localhost:8000")


@pytest.fixture
def client(check_server):
    return LatticeClient(server_url=SERVER_URL)


@pytest.mark.integration
class TestBatchingIntegration:
    """Integration tests for task batching."""

    def test_batchable_task_definition(self):
        """Test that @task decorator accepts batch parameters."""
        @task(
            inputs=["texts"],
            outputs=["embeddings"],
            batch_size=32,
            batch_timeout=0.1,
        )
        def embed_texts(params):
            """Simulate embedding generation."""
            texts = params.get("texts", [])
            if isinstance(texts, list):
                return {"embeddings": [[0.1] * 768 for _ in texts]}
            return {"embeddings": [[0.1] * 768]}

        metadata = embed_texts._lattice_task_metadata
        assert metadata.batch_config.enabled is True
        assert metadata.batch_config.batch_size == 32
        assert metadata.batch_config.batch_timeout == 0.1

    def test_batchable_task_workflow(self, client):
        """Test adding batchable tasks to a workflow."""
        @task(
            inputs=["text"],
            outputs=["embedding"],
            batch_size=4,
            batch_timeout=0.5,
        )
        def embed_text(params):
            text = params.get("text", "")
            # Simulate embedding generation
            return {"embedding": [len(text) * 0.1] * 768}

        workflow = client.create_workflow()

        # Add multiple embedding tasks
        tasks = []
        for i in range(4):
            t = workflow.add_task(
                task_func=embed_text,
                inputs={"text": f"Sample text {i}"},
            )
            tasks.append(t)

        assert len(tasks) == 4
        for t in tasks:
            assert t.task_id is not None

    def test_non_batchable_task_unaffected(self, client):
        """Test that non-batchable tasks work normally."""
        @task(inputs=["x"], outputs=["y"])
        def simple_task(params):
            return {"y": params["x"] * 2}

        workflow = client.create_workflow()
        t = workflow.add_task(
            task_func=simple_task,
            inputs={"x": 5},
        )

        assert t.task_id is not None
        metadata = simple_task._lattice_task_metadata
        assert metadata.batch_config.enabled is False


@pytest.mark.integration
class TestEmbeddingBatchScenario:
    """End-to-end tests simulating embedding workloads."""

    def test_embedding_pipeline_with_batching(self, client):
        """Test a realistic embedding pipeline with batching enabled."""
        @task(
            inputs=["documents"],
            outputs=["chunks"],
        )
        def chunk_documents(params):
            """Split documents into chunks."""
            docs = params.get("documents", [])
            chunks = []
            for doc in docs:
                # Simple chunking: split by sentences
                sentences = doc.split(". ")
                chunks.extend(sentences)
            return {"chunks": chunks}

        @task(
            inputs=["chunk"],
            outputs=["embedding"],
            batch_size=8,
            batch_timeout=0.2,
        )
        def embed_chunk(params):
            """Generate embedding for a chunk (batched)."""
            chunk = params.get("chunk", "")
            # Simulate embedding - in real scenario, this would call an embedding model
            embedding = [hash(chunk) % 100 / 100.0] * 768
            return {"embedding": embedding}

        workflow = client.create_workflow()

        # Step 1: Chunk documents
        chunk_task = workflow.add_task(
            task_func=chunk_documents,
            inputs={
                "documents": [
                    "First sentence. Second sentence. Third sentence.",
                    "Another doc. With content.",
                ]
            },
        )

        assert chunk_task.task_id is not None

        # Note: In a real scenario, we would chain embed_chunk tasks
        # that depend on chunk_task.outputs["chunks"]
        # This demonstrates the API usage pattern

    def test_parallel_embedding_tasks(self, client):
        """Test multiple embedding tasks that can be batched together."""
        @task(
            inputs=["text"],
            outputs=["embedding"],
            batch_size=4,
            batch_timeout=1.0,
        )
        def get_embedding(params):
            text = params.get("text", "")
            return {"embedding": [len(text) * 0.01] * 768}

        workflow = client.create_workflow()

        texts = [
            "Machine learning is a subset of AI.",
            "Natural language processing enables text understanding.",
            "Deep learning uses neural networks.",
            "Transformers revolutionized NLP.",
        ]

        tasks = []
        for text in texts:
            t = workflow.add_task(
                task_func=get_embedding,
                inputs={"text": text},
            )
            tasks.append(t)

        # All 4 tasks should be created
        assert len(tasks) == 4

        # With batch_size=4, these should be batched together
        # when the scheduler processes them
        for t in tasks:
            assert t.task_id is not None
            assert "embedding" in t.outputs.keys()
