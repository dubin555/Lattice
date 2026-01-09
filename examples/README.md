# Lattice Examples

Practical examples demonstrating Lattice's parallel execution capabilities for real-world applications.

## Quick Start

1. **Start Lattice server:**
   ```bash
   lattice start --head --port 8000
   ```

2. **Run any example:**
   ```bash
   cd examples/01_document_embedding_pipeline
   pip install -r requirements.txt
   python main.py
   ```

## Examples Overview

| Example | Description | Use Case |
|---------|-------------|----------|
| [01_document_embedding_pipeline](./01_document_embedding_pipeline) | Parallel embedding generation | RAG applications |
| [02_pdf_processing_pipeline](./02_pdf_processing_pipeline) | Document analysis pipeline | Enterprise document processing |
| [03_data_analysis_pipeline](./03_data_analysis_pipeline) | Parallel data science tasks | Data engineering & ML |

## Example Details

### 01 - Document Embedding Pipeline
**Dependencies:** `sentence-transformers`

Generate document embeddings in parallel for RAG (Retrieval-Augmented Generation) applications.

```
Documents -> Chunk -> [Parallel Embedding] -> Vector Index
```

### 02 - PDF Processing Pipeline  
**Dependencies:** `nltk`

Process multiple documents with parallel extraction and analysis (keywords, statistics, summarization).

```
PDFs -> [Parallel Extract] -> [Parallel Analysis] -> Report
```

### 03 - Data Analysis Pipeline
**Dependencies:** `pandas`, `numpy`, `scikit-learn`

Run independent data analysis tasks concurrently: cleaning, statistics, anomaly detection, feature engineering.

```
Load Data -> [Clean | Stats | Anomaly | Features] -> Report
```

## Key Concepts

### Task Declaration
```python
from lattice import task

@task(
    inputs=["documents"],
    outputs=["embeddings"],
    resources={"cpu": 2, "cpu_mem": 2048}
)
def generate_embeddings(params):
    docs = params.get("documents")
    # ... processing
    return {"embeddings": vectors}
```

### Workflow Construction
```python
from lattice import LatticeClient

client = LatticeClient("http://localhost:8000")
workflow = client.create_workflow()

# Tasks with dependencies are parallelized automatically
task_a = workflow.add_task(load_data, inputs={"path": "data.csv"})
task_b = workflow.add_task(analyze, inputs={"data": task_a.outputs["data"]})
task_c = workflow.add_task(detect, inputs={"data": task_a.outputs["data"]})
# task_b and task_c run in parallel
```

### Execution
```python
run_id = workflow.run()
results = workflow.get_results(run_id)
```

## Scaling Up

Add more workers for increased parallelism:

```bash
# On additional machines
lattice start --worker --addr HEAD_IP:HEAD_PORT
```
