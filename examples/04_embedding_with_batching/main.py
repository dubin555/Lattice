"""
Document Embedding with Batching - Optimized GPU Utilization
=============================================================

This example demonstrates the batching feature in Lattice, which is designed
to improve GPU utilization for tasks like embedding generation.

When to use batching:
- Embedding generation (models without built-in batching like some sentence-transformers)
- Image processing pipelines
- Any workload where the backend doesn't auto-batch

When NOT to use batching (backend handles it):
- vLLM inference (has continuous batching)
- TGI inference (has dynamic batching)

Configuration Methods:
1. Task-level: @task(batch_size=32, batch_timeout=0.1)
2. Rule-based: BatchRule with pattern matching (prefix, regex)

Usage:
    1. Start Lattice server: lattice start --head --port 8000
    2. Run: python main.py
"""

import time
import hashlib
from typing import List, Dict, Any
from lattice import LatticeClient, task
from lattice.config.defaults import BatchRule


# Sample texts for embedding
SAMPLE_TEXTS = [
    "Machine learning enables systems to learn from experience.",
    "Deep learning uses neural networks with many layers.",
    "Natural language processing helps computers understand text.",
    "Computer vision trains machines to interpret visual data.",
    "Reinforcement learning optimizes through trial and error.",
    "Neural networks process information through connected nodes.",
    "Data preprocessing transforms raw data into clean datasets.",
    "Model evaluation requires appropriate metrics for each task.",
    "Transfer learning applies knowledge from one domain to another.",
    "Federated learning trains models across decentralized data.",
    "AutoML automates the machine learning pipeline.",
    "Explainable AI makes model decisions interpretable.",
]


def simple_embedding(text: str, dim: int = 768) -> List[float]:
    """Generate a simple hash-based embedding for demonstration."""
    hash_bytes = hashlib.sha512(text.encode()).digest()
    values = []
    for i in range(dim):
        byte_val = hash_bytes[i % len(hash_bytes)]
        values.append((byte_val / 255.0) * 2 - 1)
    return values


# =============================================================================
# Method 1: Task-level batching configuration
# =============================================================================

@task(
    inputs=["text"],
    outputs=["embedding"],
    resources={"cpu": 1, "gpu": 0},
    batch_size=4,        # Collect up to 4 tasks before executing as a batch
    batch_timeout=0.1,   # Or trigger after 0.1 seconds, whichever comes first
)
def embed_text_batched(params: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Generate embeddings for text - with batching enabled.

    When batched, this function receives a LIST of param dicts and should
    return a LIST of result dicts.
    """
    # Handle both single input (non-batched) and batch input
    if isinstance(params, dict):
        # Single input mode
        text = params.get("text", "")
        embedding = simple_embedding(text)
        return {"embedding": embedding}

    # Batch mode - params is a list
    print(f"[Embed] Processing batch of {len(params)} texts...")

    results = []
    for p in params:
        text = p.get("text", "")
        embedding = simple_embedding(text)
        results.append({"embedding": embedding})

    print(f"[Embed] Batch complete: {len(results)} embeddings generated")
    return results


# For comparison: non-batched version
@task(
    inputs=["text"],
    outputs=["embedding"],
    resources={"cpu": 1, "gpu": 0},
)
def embed_text_single(params: Dict[str, Any]) -> Dict[str, Any]:
    """Generate embedding for single text - no batching."""
    text = params.get("text", "")
    embedding = simple_embedding(text)
    return {"embedding": embedding}


# =============================================================================
# Method 2: Rule-based batching (configured at server level)
# =============================================================================

# BatchRules can be configured when starting the scheduler:
#
# rules = [
#     BatchRule(
#         pattern="embed_",          # Match task names starting with "embed_"
#         match_type="prefix",       # "exact", "prefix", or "regex"
#         batch_size=32,
#         batch_timeout=0.1,
#         group_key="embedding_group",  # Optional: group multiple task types
#     ),
#     BatchRule(
#         pattern=".*_embedding$",   # Match task names ending with "_embedding"
#         match_type="regex",
#         batch_size=16,
#     ),
# ]


def demo_batched_workflow():
    """Demonstrate batched embedding workflow."""
    print("\n" + "=" * 60)
    print("Demo: Batched Embedding Workflow")
    print("=" * 60)

    client = LatticeClient("http://localhost:8000")
    workflow = client.create_workflow()

    print(f"\nAdding {len(SAMPLE_TEXTS)} embedding tasks with batch_size=4...")

    tasks = []
    for text in SAMPLE_TEXTS:
        t = workflow.add_task(
            embed_text_batched,
            inputs={"text": text},
        )
        tasks.append(t)

    print(f"Created {len(tasks)} tasks")
    print("With batch_size=4, these will be processed in ~3 batches")

    start_time = time.time()
    run_id = workflow.run()
    results = workflow.get_results(run_id, verbose=False)
    elapsed = time.time() - start_time

    embedding_count = 0
    for msg in results:
        if msg.get("type") == "finish_task":
            embedding_count += 1

    print(f"\nCompleted: {embedding_count} embeddings in {elapsed:.2f}s")
    return elapsed


def demo_non_batched_workflow():
    """Demonstrate non-batched embedding workflow for comparison."""
    print("\n" + "=" * 60)
    print("Demo: Non-Batched Embedding Workflow (Comparison)")
    print("=" * 60)

    client = LatticeClient("http://localhost:8000")
    workflow = client.create_workflow()

    print(f"\nAdding {len(SAMPLE_TEXTS)} embedding tasks without batching...")

    tasks = []
    for text in SAMPLE_TEXTS:
        t = workflow.add_task(
            embed_text_single,
            inputs={"text": text},
        )
        tasks.append(t)

    print(f"Created {len(tasks)} tasks")
    print("Each task will be processed individually")

    start_time = time.time()
    run_id = workflow.run()
    results = workflow.get_results(run_id, verbose=False)
    elapsed = time.time() - start_time

    embedding_count = 0
    for msg in results:
        if msg.get("type") == "finish_task":
            embedding_count += 1

    print(f"\nCompleted: {embedding_count} embeddings in {elapsed:.2f}s")
    return elapsed


def main():
    print("=" * 60)
    print("Lattice Batching Feature Demo")
    print("=" * 60)
    print("""
Batching is useful for:
- Embedding generation (when model doesn't auto-batch)
- Image processing pipelines
- Any GPU workload without built-in batching

Configuration options:
1. @task(batch_size=32, batch_timeout=0.1)  - Task-level
2. BatchRule(pattern="embed_", ...)         - Rule-based (server config)

The scheduler collects tasks and triggers a batch when:
- batch_size is reached, OR
- batch_timeout expires (whichever comes first)
""")

    try:
        # Run batched demo
        batched_time = demo_batched_workflow()

        # Run non-batched demo for comparison
        non_batched_time = demo_non_batched_workflow()

        print("\n" + "=" * 60)
        print("Summary")
        print("=" * 60)
        print(f"Batched:     {batched_time:.2f}s")
        print(f"Non-batched: {non_batched_time:.2f}s")

        if batched_time < non_batched_time:
            speedup = non_batched_time / batched_time
            print(f"Batching provided {speedup:.1f}x speedup")

    except Exception as e:
        print(f"\nError: {e}")
        print("\nMake sure Lattice server is running:")
        print("  lattice start --head --port 8000")


if __name__ == "__main__":
    main()
