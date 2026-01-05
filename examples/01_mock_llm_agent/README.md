# Mock LLM Agent Workflow

This example demonstrates how Lattice accelerates LLM agent workflows by executing independent tool calls in parallel.

## Overview

In typical LLM agent architectures, the agent analyzes a query, calls multiple tools, and synthesizes the results. These tool calls are often independent and can be parallelized.

```
User Query
    ↓
Task A: Query Analysis (2s)
    ↓
┌───────────┼───────────┐
↓           ↓           ↓
Task B     Task C     Task D     ← Parallel execution
(Search)  (Database) (Calculator)
  3s         3s         3s
↓           ↓           ↓
└───────────┼───────────┘
            ↓
Task E: Response Synthesis (2s)
```

## Performance

| Execution Mode | Time | Speedup |
|----------------|------|---------|
| Sequential | ~13s | 1.0x |
| Lattice Parallel | ~7s | **1.9x** |

## Requirements

**None!** This example uses only `time.sleep()` to simulate LLM API latency.

## Usage

1. Start Lattice server:
   ```bash
   lattice start --head --port 8000
   ```

2. Run the example:
   ```bash
   python main.py
   ```

## Key Takeaways

- **Zero code changes** to your task logic - just add the `@task` decorator
- **Automatic parallelization** - Lattice detects independent tasks from the DAG
- **Resource management** - Each task specifies its resource requirements
- **Real-world applicable** - This pattern applies to any LLM agent with multiple tool calls
