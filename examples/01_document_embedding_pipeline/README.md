# Document Embedding Pipeline

A practical RAG (Retrieval-Augmented Generation) example demonstrating parallel document embedding generation with Lattice.

## Use Case

In RAG applications, generating embeddings for large document collections is often a bottleneck. This example shows how Lattice can parallelize embedding generation across multiple workers.

## Workflow

```
Documents -> Load & Chunk -> [Parallel Embedding Generation] -> Build Vector Index
```

## Requirements

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Start Lattice server
lattice start --head --port 8000

# Run the pipeline
python main.py
```

## Performance

With 4 parallel embedding workers, this pipeline achieves significant speedup compared to sequential processing, especially beneficial when processing large document sets.
