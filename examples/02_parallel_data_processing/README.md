# Parallel Data Processing

This example demonstrates the **fan-out/fan-in** pattern - a fundamental pattern in distributed data processing.

## Overview

Data processing pipelines often follow this pattern:
1. Split data into chunks
2. Process each chunk independently (parallelizable!)
3. Aggregate results

```
Raw Data (10,000 points)
         ↓
Task A: Split Data (1s)
         ↓
    ┌────┬────┬────┐
    ↓    ↓    ↓    ↓
   B0   B1   B2   B3   ← Parallel processing
  (3s) (3s) (3s) (3s)
    ↓    ↓    ↓    ↓
    └────┴────┴────┘
         ↓
Task C: Aggregate (1s)
```

## Performance

| Execution Mode | Time | Speedup |
|----------------|------|---------|
| Sequential | ~14s | 1.0x |
| Lattice Parallel | ~5s | **2.8x** |

## Requirements

**None!** Uses only Python standard library.

## Usage

1. Start Lattice server:
   ```bash
   lattice start --head --port 8000
   ```

2. Run the example:
   ```bash
   python main.py
   ```

## What It Does

1. **Generates** 10,000 sample data points (with some outliers)
2. **Splits** into 4 chunks
3. **Computes** statistics for each chunk in parallel:
   - Mean, standard deviation
   - Min/max values
   - Outlier detection
4. **Aggregates** into a global statistical report

## Real-World Applications

This pattern applies to:
- **ETL pipelines** - Transform data in parallel batches
- **Log analysis** - Process log files from multiple servers
- **Feature engineering** - Compute features across data partitions
- **Report generation** - Aggregate metrics from multiple sources
