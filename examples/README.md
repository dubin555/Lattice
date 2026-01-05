# Lattice Examples

This directory contains examples demonstrating Lattice's parallel execution capabilities.

## Quick Start

1. **Start Lattice server:**
   ```bash
   lattice start --head --port 8000
   ```

2. **Run any example:**
   ```bash
   cd examples/01_mock_llm_agent
   python main.py
   ```

## Examples Overview

| Example | Description | Dependencies | Speedup |
|---------|-------------|--------------|---------|
| [01_mock_llm_agent](./01_mock_llm_agent) | LLM agent with parallel tool calls | None | ~1.9x |
| [02_parallel_data_processing](./02_parallel_data_processing) | Fan-out/fan-in data processing | None | ~2.8x |
| [03_web_scraping_pipeline](./03_web_scraping_pipeline) | Multi-stage web scraping | None | ~3.25x |
| [04_image_batch_processing](./04_image_batch_processing) | Batch image processing | Pillow (optional) | ~3.1x |

## Example Details

### 01 - Mock LLM Agent
**Zero dependencies** - Perfect for understanding Lattice basics.

Simulates a typical LLM agent workflow where multiple tools (search, database, calculator) are called in parallel after query analysis.

```
Query → Analyze → [Search | Database | Calculator] → Synthesize
         2s            3s     3s        3s              2s
```

### 02 - Parallel Data Processing
**Zero dependencies** - Shows the fan-out/fan-in pattern.

Demonstrates splitting data into chunks, processing each in parallel, and aggregating results.

```
Split → [Process × 4] → Aggregate
  1s        3s each         1s
```

### 03 - Web Scraping Pipeline
**Zero dependencies** - Multi-stage parallel pipeline.

Shows how to parallelize both fetching and parsing stages of a web scraping workflow.

```
[Fetch × 4] → [Parse × 4] → Aggregate
   2s each       1s each        1s
```

### 04 - Image Batch Processing
**Optional: Pillow** - Resource-aware batch processing.

Demonstrates image processing with CPU resource specifications. Works with mock images if Pillow isn't installed.

```
[Resize × 4] → [Filter × 4] → Gallery
   1s each       1.5s each       1s
```

## Key Concepts Demonstrated

### 1. Task Declaration
```python
from lattice import task

@task(
    inputs=["query"],           # Input parameter names
    outputs=["result"],         # Output parameter names
    resources={"cpu": 2}        # Resource requirements
)
def my_task(params):
    query = params.get("query")
    return {"result": f"Processed: {query}"}
```

### 2. Workflow Construction
```python
from lattice import LatticeClient

client = LatticeClient("http://localhost:8000")
workflow = client.create_workflow()

# Add tasks and connect them
task_a = workflow.add_task(analyze, inputs={"query": "hello"})
task_b = workflow.add_task(process, inputs={"data": task_a.outputs["result"]})
```

### 3. Execution
```python
run_id = workflow.run()
results = workflow.get_results(run_id)
```

## Performance Tips

1. **Maximize parallelism** - Design DAGs with independent branches
2. **Right-size resources** - Specify accurate CPU/GPU requirements
3. **Batch similar work** - Group similar tasks for better scheduling
4. **Use distributed mode** - Add worker nodes for more parallelism:
   ```bash
   lattice start --worker --addr HEAD_IP:HEAD_PORT
   ```
