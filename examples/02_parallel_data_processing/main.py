"""
Parallel Data Processing - Demonstrates Fan-Out/Fan-In Pattern
===============================================================

This example shows how Lattice handles parallel data processing tasks,
a common pattern in data pipelines where multiple data chunks are
processed independently and then aggregated.

Workflow Structure:
    Raw Data Input
         ↓
    Task A: Data Splitting (split into 4 chunks)
         ↓
    ┌────┬────┬────┐
    ↓    ↓    ↓    ↓
   B1   B2   B3   B4   ← Parallel processing (each 3s)
    ↓    ↓    ↓    ↓
    └────┴────┴────┘
         ↓
    Task C: Aggregation & Statistics

Performance:
    - Sequential: 1 + 4×3 + 1 = 14 seconds
    - Lattice Parallel: 1 + 3 + 1 = 5 seconds (2.8x speedup)

Requirements: None (uses only standard library)

Usage:
    1. Start Lattice server: lattice start --head --port 8000
    2. Run this script: python main.py
"""

import time
import random
import statistics
from lattice import LatticeClient, task


@task(
    inputs=["raw_data"],
    outputs=["chunk_0", "chunk_1", "chunk_2", "chunk_3", "chunk_count"],
    resources={"cpu": 1, "cpu_mem": 256}
)
def split_data(params):
    """
    Task A: Split raw data into chunks for parallel processing.
    """
    raw_data = params.get("raw_data")
    print(f"[Task A] Splitting {len(raw_data)} data points into chunks...")
    
    time.sleep(1)
    
    chunk_size = len(raw_data) // 4
    chunks = [
        raw_data[i * chunk_size:(i + 1) * chunk_size]
        for i in range(4)
    ]
    
    if len(raw_data) % 4:
        chunks[-1].extend(raw_data[4 * chunk_size:])
    
    print(f"[Task A] ✓ Created 4 chunks: {[len(c) for c in chunks]}")
    
    return {
        "chunk_0": chunks[0],
        "chunk_1": chunks[1],
        "chunk_2": chunks[2],
        "chunk_3": chunks[3],
        "chunk_count": 4
    }


@task(
    inputs=["chunk", "chunk_id"],
    outputs=["processed_stats"],
    resources={"cpu": 2, "cpu_mem": 512}
)
def process_chunk(params):
    """
    Task B: Process a single data chunk (compute-intensive).
    This represents any CPU-bound data processing task.
    """
    chunk = params.get("chunk")
    chunk_id = params.get("chunk_id")
    
    print(f"[Task B{chunk_id}] Processing chunk with {len(chunk)} items...")
    
    time.sleep(3)
    
    chunk_mean = sum(chunk) / len(chunk)
    chunk_std = statistics.stdev(chunk) if len(chunk) > 1 else 0
    chunk_min = min(chunk)
    chunk_max = max(chunk)
    chunk_sum = sum(chunk)
    
    outliers = [x for x in chunk if abs(x - chunk_mean) > 2 * chunk_std]
    
    stats = {
        "chunk_id": chunk_id,
        "count": len(chunk),
        "sum": chunk_sum,
        "mean": chunk_mean,
        "std": chunk_std,
        "min": chunk_min,
        "max": chunk_max,
        "outlier_count": len(outliers),
    }
    
    print(f"[Task B{chunk_id}] ✓ Processed: mean={chunk_mean:.2f}, std={chunk_std:.2f}")
    
    return {"processed_stats": stats}


@task(
    inputs=["stats_0", "stats_1", "stats_2", "stats_3"],
    outputs=["final_report"],
    resources={"cpu": 1, "cpu_mem": 256}
)
def aggregate_results(params):
    """
    Task C: Aggregate all chunk statistics into final report.
    """
    print(f"[Task C] Aggregating results from all chunks...")
    
    all_stats = [
        params.get("stats_0"),
        params.get("stats_1"),
        params.get("stats_2"),
        params.get("stats_3"),
    ]
    
    time.sleep(1)
    
    total_count = sum(s["count"] for s in all_stats)
    total_sum = sum(s["sum"] for s in all_stats)
    global_mean = total_sum / total_count
    global_min = min(s["min"] for s in all_stats)
    global_max = max(s["max"] for s in all_stats)
    total_outliers = sum(s["outlier_count"] for s in all_stats)
    
    combined_variance = sum(
        s["count"] * (s["std"] ** 2 + (s["mean"] - global_mean) ** 2)
        for s in all_stats
    ) / total_count
    global_std = combined_variance ** 0.5
    
    report = {
        "total_records": total_count,
        "global_mean": round(global_mean, 4),
        "global_std": round(global_std, 4),
        "global_min": global_min,
        "global_max": global_max,
        "total_outliers": total_outliers,
        "chunks_processed": len(all_stats),
    }
    
    print(f"[Task C] ✓ Final report generated")
    
    return {"final_report": report}


def generate_sample_data(n=10000):
    """Generate sample numerical data with some outliers."""
    random.seed(42)
    
    normal_data = [random.gauss(100, 15) for _ in range(int(n * 0.95))]
    outliers = [random.gauss(200, 10) for _ in range(int(n * 0.05))]
    
    data = normal_data + outliers
    random.shuffle(data)
    
    return data


def main():
    print("=" * 60)
    print("🔢 Lattice Parallel Data Processing Demo")
    print("=" * 60)
    print("""
This demo shows how Lattice parallelizes data processing pipelines
using the fan-out/fan-in pattern.

Workflow:
    Split Data → [Process Chunk 1-4 in parallel] → Aggregate Results
    """)
    
    sample_data = generate_sample_data(10000)
    print(f"\n📊 Generated {len(sample_data)} sample data points")
    
    print("\n" + "=" * 60)
    print("Running with LATTICE parallel execution...")
    print("=" * 60)
    
    start_time = time.time()
    
    client = LatticeClient("http://localhost:8000")
    workflow = client.create_workflow()
    
    task_split = workflow.add_task(
        split_data,
        inputs={"raw_data": sample_data}
    )
    
    process_tasks = []
    for i in range(4):
        task_process = workflow.add_task(
            process_chunk,
            inputs={
                "chunk": task_split.outputs[f"chunk_{i}"],
                "chunk_id": i
            },
            task_name=f"process_chunk_{i}"
        )
        process_tasks.append(task_process)
    
    task_aggregate = workflow.add_task(
        aggregate_results,
        inputs={
            "stats_0": process_tasks[0].outputs["processed_stats"],
            "stats_1": process_tasks[1].outputs["processed_stats"],
            "stats_2": process_tasks[2].outputs["processed_stats"],
            "stats_3": process_tasks[3].outputs["processed_stats"],
        }
    )
    
    print("\n📊 Workflow Structure:")
    print("       Task A (Split)")
    print("           ↓")
    print("    ┌──┬──┬──┬──┐")
    print("    ↓  ↓  ↓  ↓")
    print("   B0 B1 B2 B3   ← Parallel!")
    print("    ↓  ↓  ↓  ↓")
    print("    └──┴──┴──┴──┘")
    print("           ↓")
    print("       Task C (Aggregate)")
    print()
    
    run_id = workflow.run()
    results = workflow.get_results(run_id, verbose=False)
    
    elapsed = time.time() - start_time
    
    for msg in results:
        if msg.get("type") == "task_complete":
            output = msg.get("output", {})
            if "final_report" in output:
                report = output["final_report"]
                print("\n📋 Final Statistical Report:")
                print(f"   Total Records: {report['total_records']:,}")
                print(f"   Global Mean: {report['global_mean']}")
                print(f"   Global Std Dev: {report['global_std']}")
                print(f"   Range: [{report['global_min']:.2f}, {report['global_max']:.2f}]")
                print(f"   Outliers Detected: {report['total_outliers']}")
    
    print(f"\n[Lattice] Total time: {elapsed:.1f} seconds")
    
    print("\n" + "=" * 60)
    print("📈 PERFORMANCE COMPARISON")
    print("=" * 60)
    sequential_time = 1 + 4 * 3 + 1
    print(f"""
Sequential execution (baseline): ~{sequential_time} seconds
Lattice parallel execution:      ~{elapsed:.1f} seconds

Speedup: {sequential_time / elapsed:.1f}x faster!

With more data chunks or longer processing times, the speedup
would be even more significant.
""")


if __name__ == "__main__":
    main()
