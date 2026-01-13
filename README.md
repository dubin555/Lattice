<h1 align="center">Lattice</h1>

<p align="center">
  <b>Task-level Distributed Framework for LLM Agents</b>
</p>

<p align="center">
    <a href="https://github.com/dubin555/Lattice/blob/main/LICENSE">
        <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
    </a>
</p>

<p align="center">
    <a href="./README_ZH.md">中文</a> | English
</p>

## The Problem

**LLM Agent workflows suffer from unnecessary sequential execution.**

Consider a typical agent workflow:

```
User Query → Analyze Intent → [Search API] → [Database Query] → [Calculator] → Generate Response
                                   3s              3s               3s
```

These three tool calls are **independent** — yet most frameworks execute them **sequentially** (9 seconds total).

With Lattice, they run **in parallel** (3 seconds total):

```
                              ┌─ Search API ──┐
User Query → Analyze Intent ──┼─ Database ────┼─→ Generate Response
                              └─ Calculator ──┘
                                   3s (parallel)
```

## The Solution

Lattice provides **automatic task-level parallelism** for LLM agent workflows:

1. **Declare tasks** with `@task` decorator (inputs, outputs, resources)
2. **Build DAG** by connecting task outputs to inputs
3. **Execute** — Lattice automatically parallelizes independent tasks

```python
from lattice import LatticeClient, task

@task(inputs=["query"], outputs=["results"])
def search(params):
    return {"results": call_search_api(params["query"])}

@task(inputs=["query"], outputs=["data"])
def database(params):
    return {"data": query_database(params["query"])}

# These tasks run in parallel automatically
client = LatticeClient("http://localhost:8000")
workflow = client.create_workflow()

analyze = workflow.add_task(analyze_intent, inputs={"query": user_query})
search_task = workflow.add_task(search, inputs={"query": analyze.outputs["query"]})
db_task = workflow.add_task(database, inputs={"query": analyze.outputs["query"]})  # Parallel!
final = workflow.add_task(synthesize, inputs={
    "search": search_task.outputs["results"],
    "data": db_task.outputs["data"]
})
```

## Why Not Just Use...?

| Solution | Gap |
|----------|-----|
| **Ray** | Low-level; no DAG abstraction for agents |
| **Celery** | Task queue without DAG dependency management |
| **Airflow/Prefect** | Batch ETL focus; not for real-time agent interactions |
| **LangGraph** | Defines DAG but executes sequentially; **Lattice can be its parallel backend** |
| **asyncio** | Manual concurrency; no distributed execution or resource management |

**Lattice fills the gap**: declarative DAG + automatic parallelism + distributed execution + resource-aware scheduling.

## Quick Start

### Install

```bash
pip install lattice-agent
# or from source
git clone https://github.com/dubin555/Lattice.git && cd Lattice && pip install -e .
```

### Launch Server

```bash
lattice start --head --port 8000
```

### Run a Workflow

```python
from lattice import LatticeClient, task

@task(inputs=["x"], outputs=["y"])
def double(params):
    return {"y": params["x"] * 2}

client = LatticeClient("http://localhost:8000")
workflow = client.create_workflow()
t = workflow.add_task(double, inputs={"x": 21})

run_id = workflow.run()
results = workflow.get_results(run_id)
print(results)  # y = 42
```

## Examples

Real-world examples in [`examples/`](./examples):

| Example | Description |
|---------|-------------|
| [Document Embedding Pipeline](./examples/01_document_embedding_pipeline) | Parallel embedding generation for RAG |
| [PDF Processing Pipeline](./examples/02_pdf_processing_pipeline) | Multi-document analysis with parallel extraction |
| [Data Analysis Pipeline](./examples/03_data_analysis_pipeline) | Concurrent data science tasks |

## LangGraph Integration

Run LangGraph workflows on Lattice for automatic parallelism:

```python
from lattice import LangGraphClient

client = LangGraphClient("http://localhost:8000")

@client.task(cpu=2, memory=4096)
def process_node(state):
    # Your LangGraph node logic
    return {"processed": True}
```

**Synchronous by Design**: The LangGraph client uses synchronous blocking calls intentionally. This is the right choice because:

- **Outer layer (FastAPI) is async** — multiple requests can be handled concurrently
- **Execution engine (Ray) is async** — tasks run in parallel on distributed workers
- **LangGraph call site blocks** — follows natural function call semantics, keeps workflow code simple

An async callback pattern would add complexity (state machines, callback registration, result assembly) with little benefit — true concurrency is already handled by the layers above and below.

## Architecture

```
Client (@task, workflow.add_task)
         │ HTTP
         ▼
   ┌─────────────────────────────┐
   │       Lattice Server        │
   │  Orchestrator → Scheduler   │
   │     Resource Manager        │
   └─────────────┬───────────────┘
                 │ Ray
    ┌────────────┼────────────┐
    ▼            ▼            ▼
 Worker 1    Worker 2    Worker N
```

## Distributed Mode

Scale out by adding workers:

```bash
# Head node
lattice start --head --port 8000

# Worker nodes (on other machines)
lattice start --worker --addr HEAD_IP:8000
```

## Sandbox Execution

Secure task execution for untrusted code:

```bash
lattice start --head --port 8000 --sandbox seccomp  # Linux
lattice start --head --port 8000 --sandbox subprocess  # Cross-platform
```

## License

MIT License — see [LICENSE](LICENSE).

---

> Built upon [Maze](https://github.com/QinbinLi/Maze) with enhancements for sandbox isolation, resource management, and LangGraph integration.
