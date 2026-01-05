"""
Mock LLM Agent Workflow - Demonstrates Lattice Parallel Execution
==================================================================

This example simulates a typical LLM agent workflow with multiple parallel
tool calls. It uses time.sleep() to simulate LLM API latency, making it
easy to see the performance improvement from parallel execution.

Workflow Structure:
    User Query
        ↓
    Task A: Query Analysis (2s)
        ↓
    ┌───────────┼───────────┐
    ↓           ↓           ↓
  Task B      Task C      Task D     ← Parallel execution (each 3s)
  (Search)   (Database)  (Calculator)
    ↓           ↓           ↓
    └───────────┼───────────┘
                ↓
    Task E: Response Synthesis (2s)

Performance:
    - Sequential: 2 + 3 + 3 + 3 + 2 = 13 seconds
    - Lattice Parallel: 2 + 3 + 2 = 7 seconds (1.9x speedup)

Requirements: None (uses only standard library)

Usage:
    1. Start Lattice server: lattice start --head --port 8000
    2. Run this script: python main.py
"""

import time
from lattice import LatticeClient, task


@task(
    inputs=["query"],
    outputs=["intent", "entities", "tool_requests"],
    resources={"cpu": 1, "cpu_mem": 512}
)
def analyze_query(params):
    """
    Task A: Analyze user query to determine intent and required tools.
    Simulates LLM call for query understanding.
    """
    query = params.get("query")
    print(f"[Task A] Analyzing query: {query}")
    
    time.sleep(2)
    
    result = {
        "intent": "information_retrieval",
        "entities": ["Python", "performance", "optimization"],
        "tool_requests": ["search", "database", "calculator"]
    }
    
    print(f"[Task A] ✓ Analysis complete: {result['intent']}")
    return result


@task(
    inputs=["query", "entities"],
    outputs=["search_results"],
    resources={"cpu": 1, "cpu_mem": 512}
)
def search_tool(params):
    """
    Task B: Search for relevant information.
    Simulates calling a search API.
    """
    query = params.get("query")
    entities = params.get("entities")
    print(f"[Task B] Searching for: {entities}")
    
    time.sleep(3)
    
    results = [
        {"title": "Python Performance Tips", "relevance": 0.95},
        {"title": "Optimization Techniques", "relevance": 0.87},
        {"title": "Best Practices Guide", "relevance": 0.82},
    ]
    
    print(f"[Task B] ✓ Found {len(results)} search results")
    return {"search_results": results}


@task(
    inputs=["entities"],
    outputs=["database_results"],
    resources={"cpu": 1, "cpu_mem": 512}
)
def database_tool(params):
    """
    Task C: Query internal database for related data.
    Simulates database lookup with some latency.
    """
    entities = params.get("entities")
    print(f"[Task C] Querying database for: {entities}")
    
    time.sleep(3)
    
    results = {
        "related_docs": 42,
        "last_updated": "2024-01-15",
        "categories": ["programming", "performance"],
    }
    
    print(f"[Task C] ✓ Database query complete: {results['related_docs']} docs found")
    return {"database_results": results}


@task(
    inputs=["query"],
    outputs=["calculation_results"],
    resources={"cpu": 1, "cpu_mem": 512}
)
def calculator_tool(params):
    """
    Task D: Perform calculations based on query.
    Simulates computational analysis.
    """
    query = params.get("query")
    print(f"[Task D] Performing calculations...")
    
    time.sleep(3)
    
    results = {
        "estimated_improvement": "35%",
        "confidence": 0.89,
        "sample_size": 1000,
    }
    
    print(f"[Task D] ✓ Calculation complete: {results['estimated_improvement']} improvement")
    return {"calculation_results": results}


@task(
    inputs=["query", "intent", "search_results", "database_results", "calculation_results"],
    outputs=["final_response"],
    resources={"cpu": 1, "cpu_mem": 512}
)
def synthesize_response(params):
    """
    Task E: Synthesize all tool results into a coherent response.
    Simulates LLM call for response generation.
    """
    print(f"[Task E] Synthesizing response from all tool results...")
    
    query = params.get("query")
    intent = params.get("intent")
    search_results = params.get("search_results")
    database_results = params.get("database_results")
    calculation_results = params.get("calculation_results")
    
    time.sleep(2)
    
    response = f"""
Based on your query about "{query}", I found the following:

📊 Search Results:
   - Found {len(search_results)} relevant articles
   - Top result: {search_results[0]['title']} (relevance: {search_results[0]['relevance']})

📁 Database Information:
   - {database_results['related_docs']} related documents available
   - Categories: {', '.join(database_results['categories'])}

🔢 Analysis Results:
   - Estimated improvement: {calculation_results['estimated_improvement']}
   - Confidence level: {calculation_results['confidence']}

Intent detected: {intent}
"""
    
    print(f"[Task E] ✓ Response synthesized successfully")
    return {"final_response": response}


def run_sequential_baseline():
    """Run tasks sequentially to establish baseline timing."""
    print("\n" + "=" * 60)
    print("Running SEQUENTIAL baseline (simulated)...")
    print("=" * 60)
    
    start_time = time.time()
    
    time.sleep(2)
    print("[Sequential] Task A: Query Analysis (2s)")
    
    time.sleep(3)
    print("[Sequential] Task B: Search (3s)")
    
    time.sleep(3)
    print("[Sequential] Task C: Database (3s)")
    
    time.sleep(3)
    print("[Sequential] Task D: Calculator (3s)")
    
    time.sleep(2)
    print("[Sequential] Task E: Synthesis (2s)")
    
    elapsed = time.time() - start_time
    print(f"\n[Sequential] Total time: {elapsed:.1f} seconds")
    return elapsed


def run_with_lattice():
    """Run workflow with Lattice parallel execution."""
    print("\n" + "=" * 60)
    print("Running with LATTICE parallel execution...")
    print("=" * 60)
    
    start_time = time.time()
    
    client = LatticeClient("http://localhost:8000")
    workflow = client.create_workflow()
    
    user_query = "How can I improve Python code performance?"
    
    task_a = workflow.add_task(
        analyze_query,
        inputs={"query": user_query}
    )
    
    task_b = workflow.add_task(
        search_tool,
        inputs={
            "query": user_query,
            "entities": task_a.outputs["entities"]
        }
    )
    
    task_c = workflow.add_task(
        database_tool,
        inputs={"entities": task_a.outputs["entities"]}
    )
    
    task_d = workflow.add_task(
        calculator_tool,
        inputs={"query": user_query}
    )
    
    task_e = workflow.add_task(
        synthesize_response,
        inputs={
            "query": user_query,
            "intent": task_a.outputs["intent"],
            "search_results": task_b.outputs["search_results"],
            "database_results": task_c.outputs["database_results"],
            "calculation_results": task_d.outputs["calculation_results"],
        }
    )
    
    print("\n📊 Workflow Structure:")
    print("    Task A (Analysis)")
    print("       ↓")
    print("    ┌──┴──┬──────┐")
    print("    ↓     ↓      ↓")
    print("  Task B Task C Task D  ← Parallel!")
    print("    └──┬──┴──────┘")
    print("       ↓")
    print("    Task E (Synthesis)")
    print()
    
    run_id = workflow.run()
    results = workflow.get_results(run_id, verbose=False)
    
    elapsed = time.time() - start_time
    
    for msg in results:
        if msg.get("type") == "task_complete" and "final_response" in str(msg):
            if "output" in msg:
                print("\n📝 Final Response:")
                print(msg["output"].get("final_response", ""))
    
    print(f"\n[Lattice] Total time: {elapsed:.1f} seconds")
    return elapsed


def main():
    print("=" * 60)
    print("🚀 Lattice Mock LLM Agent Demo")
    print("=" * 60)
    print("""
This demo shows how Lattice accelerates LLM agent workflows by
executing independent tool calls in parallel.

Workflow: Query → Analysis → [Search | Database | Calculator] → Synthesis
    """)
    
    lattice_time = run_with_lattice()
    
    print("\n" + "=" * 60)
    print("📈 PERFORMANCE COMPARISON")
    print("=" * 60)
    print(f"""
Sequential execution (baseline): ~13.0 seconds
Lattice parallel execution:      ~{lattice_time:.1f} seconds

Speedup: {13.0 / lattice_time:.1f}x faster!

This improvement comes from executing Tasks B, C, and D in parallel
instead of sequentially. In real-world LLM agent applications with
many tool calls, the speedup can be even more significant.
""")


if __name__ == "__main__":
    main()
