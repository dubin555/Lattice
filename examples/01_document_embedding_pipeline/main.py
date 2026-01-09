"""
Document Embedding Pipeline - RAG Application with Parallel Processing
=======================================================================

A practical example showing how Lattice accelerates document embedding
generation for Retrieval-Augmented Generation (RAG) applications.

Workflow Structure:
    Document Files
         |
    Task A: Load & Chunk Documents
         |
    +----+----+----+
    |    |    |    |
   B0   B1   B2   B3   <- Parallel embedding generation
    |    |    |    |
    +----+----+----+
         |
    Task C: Build Vector Index

This is a common pattern in RAG pipelines where embedding generation
is the bottleneck. Lattice parallelizes embedding across document chunks.

Requirements: sentence-transformers

Usage:
    1. Start Lattice server: lattice start --head --port 8000
    2. Install deps: pip install sentence-transformers
    3. Run: python main.py
"""

import time
import os
from typing import List, Dict, Any
from lattice import LatticeClient, task

SAMPLE_DOCUMENTS = [
    {
        "id": "doc_1",
        "title": "Introduction to Machine Learning",
        "content": """Machine learning is a subset of artificial intelligence that enables 
        systems to learn and improve from experience without being explicitly programmed. 
        It focuses on developing computer programs that can access data and use it to learn 
        for themselves. The process begins with observations or data, such as examples, 
        direct experience, or instruction, to look for patterns in data and make better 
        decisions in the future."""
    },
    {
        "id": "doc_2", 
        "title": "Deep Learning Fundamentals",
        "content": """Deep learning is a subset of machine learning that uses neural networks 
        with many layers. These deep neural networks attempt to simulate the behavior of 
        the human brain in processing data and creating patterns for decision making. 
        Deep learning drives many artificial intelligence applications and services that 
        improve automation, performing analytical and physical tasks without human intervention."""
    },
    {
        "id": "doc_3",
        "title": "Natural Language Processing",
        "content": """Natural language processing is a branch of artificial intelligence 
        that helps computers understand, interpret and manipulate human language. NLP draws 
        from many disciplines, including computer science and computational linguistics, 
        in its pursuit to fill the gap between human communication and computer understanding. 
        Applications include translation, sentiment analysis, and chatbots."""
    },
    {
        "id": "doc_4",
        "title": "Computer Vision Applications",
        "content": """Computer vision is a field of artificial intelligence that trains 
        computers to interpret and understand the visual world. Using digital images from 
        cameras and videos and deep learning models, machines can accurately identify and 
        classify objects and then react to what they see. Applications range from autonomous 
        vehicles to medical imaging analysis."""
    },
]


@task(
    inputs=["documents", "chunk_size"],
    outputs=["chunks"],
    resources={"cpu": 1, "cpu_mem": 512}
)
def load_and_chunk_documents(params: Dict[str, Any]) -> Dict[str, Any]:
    """Load documents and split into chunks for parallel processing."""
    documents = params.get("documents", [])
    chunk_size = params.get("chunk_size", 200)
    
    print(f"[Load] Processing {len(documents)} documents...")
    
    chunks = []
    for doc in documents:
        text = doc["content"]
        words = text.split()
        
        for i in range(0, len(words), chunk_size):
            chunk_text = " ".join(words[i:i + chunk_size])
            chunks.append({
                "doc_id": doc["id"],
                "doc_title": doc["title"],
                "chunk_id": len(chunks),
                "text": chunk_text,
            })
    
    print(f"[Load] Created {len(chunks)} chunks from {len(documents)} documents")
    return {"chunks": chunks}


@task(
    inputs=["chunks", "model_name"],
    outputs=["embeddings"],
    resources={"cpu": 2, "cpu_mem": 2048}
)
def generate_embeddings(params: Dict[str, Any]) -> Dict[str, Any]:
    """Generate embeddings for a batch of text chunks."""
    from sentence_transformers import SentenceTransformer
    
    chunks = params.get("chunks", [])
    model_name = params.get("model_name", "all-MiniLM-L6-v2")
    
    if not chunks:
        return {"embeddings": []}
    
    batch_id = chunks[0].get("chunk_id", 0) // max(1, len(chunks))
    print(f"[Embed-{batch_id}] Generating embeddings for {len(chunks)} chunks...")
    
    start = time.time()
    model = SentenceTransformer(model_name)
    
    texts = [chunk["text"] for chunk in chunks]
    vectors = model.encode(texts, show_progress_bar=False)
    
    embeddings = []
    for chunk, vector in zip(chunks, vectors):
        embeddings.append({
            "doc_id": chunk["doc_id"],
            "doc_title": chunk["doc_title"],
            "chunk_id": chunk["chunk_id"],
            "text": chunk["text"][:100] + "...",
            "embedding": vector.tolist(),
            "embedding_dim": len(vector),
        })
    
    elapsed = time.time() - start
    print(f"[Embed-{batch_id}] Generated {len(embeddings)} embeddings in {elapsed:.2f}s")
    
    return {"embeddings": embeddings}


@task(
    inputs=["embeddings_0", "embeddings_1", "embeddings_2", "embeddings_3"],
    outputs=["index_stats"],
    resources={"cpu": 1, "cpu_mem": 1024}
)
def build_vector_index(params: Dict[str, Any]) -> Dict[str, Any]:
    """Combine all embeddings and build a simple vector index."""
    import numpy as np
    
    all_embeddings = []
    for i in range(4):
        batch = params.get(f"embeddings_{i}", [])
        if batch:
            all_embeddings.extend(batch)
    
    print(f"[Index] Building index from {len(all_embeddings)} embeddings...")
    
    if not all_embeddings:
        return {"index_stats": {"error": "No embeddings to index"}}
    
    vectors = np.array([e["embedding"] for e in all_embeddings])
    
    norms = np.linalg.norm(vectors, axis=1)
    vectors_normalized = vectors / norms[:, np.newaxis]
    
    docs_indexed = len(set(e["doc_id"] for e in all_embeddings))
    
    stats = {
        "total_vectors": len(all_embeddings),
        "embedding_dim": all_embeddings[0]["embedding_dim"],
        "documents_indexed": docs_indexed,
        "index_size_mb": round(vectors.nbytes / (1024 * 1024), 2),
        "sample_docs": list(set(e["doc_title"] for e in all_embeddings))[:5],
    }
    
    print(f"[Index] Index built: {stats['total_vectors']} vectors, {stats['documents_indexed']} docs")
    
    return {"index_stats": stats}


def main():
    print("=" * 65)
    print("Document Embedding Pipeline - RAG with Lattice")
    print("=" * 65)
    
    print(f"\nDocuments to process: {len(SAMPLE_DOCUMENTS)}")
    for doc in SAMPLE_DOCUMENTS:
        print(f"  - {doc['title']}")
    
    start_time = time.time()
    
    client = LatticeClient("http://localhost:8000")
    workflow = client.create_workflow()
    
    load_task = workflow.add_task(
        load_and_chunk_documents,
        inputs={
            "documents": SAMPLE_DOCUMENTS,
            "chunk_size": 50,
        }
    )
    
    num_workers = 4
    embed_tasks = []
    
    for i in range(num_workers):
        embed_task = workflow.add_task(
            generate_embeddings,
            inputs={
                "chunks": load_task.outputs["chunks"],
                "model_name": "all-MiniLM-L6-v2",
            },
            task_name=f"embed_batch_{i}"
        )
        embed_tasks.append(embed_task)
    
    index_task = workflow.add_task(
        build_vector_index,
        inputs={
            "embeddings_0": embed_tasks[0].outputs["embeddings"],
            "embeddings_1": embed_tasks[1].outputs["embeddings"],
            "embeddings_2": embed_tasks[2].outputs["embeddings"],
            "embeddings_3": embed_tasks[3].outputs["embeddings"],
        }
    )
    
    print("\nWorkflow Structure:")
    print("    Load & Chunk Documents")
    print("           |")
    print("    +------+------+------+")
    print("    |      |      |      |")
    print("  Embed  Embed  Embed  Embed  <- Parallel")
    print("    |      |      |      |")
    print("    +------+------+------+")
    print("           |")
    print("    Build Vector Index")
    print()
    
    run_id = workflow.run()
    results = workflow.get_results(run_id, verbose=False)
    
    elapsed = time.time() - start_time
    
    for msg in results:
        if msg.get("type") == "task_complete":
            output = msg.get("output", {})
            if "index_stats" in output:
                stats = output["index_stats"]
                print("\nVector Index Stats:")
                print(f"  Total Vectors: {stats.get('total_vectors', 'N/A')}")
                print(f"  Embedding Dim: {stats.get('embedding_dim', 'N/A')}")
                print(f"  Documents: {stats.get('documents_indexed', 'N/A')}")
                print(f"  Index Size: {stats.get('index_size_mb', 'N/A')} MB")
    
    print(f"\nTotal pipeline time: {elapsed:.2f} seconds")
    print("\nThis pipeline demonstrates parallel embedding generation,")
    print("a key optimization for RAG applications processing large document sets.")


if __name__ == "__main__":
    main()
