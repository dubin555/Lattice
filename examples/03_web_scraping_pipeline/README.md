# Web Scraping Pipeline

This example demonstrates a **multi-stage parallel pipeline** for web scraping, with both fetching and parsing stages parallelized.

## Overview

Web scraping workflows often have these stages:
1. **Fetch** multiple URLs (I/O bound, highly parallelizable)
2. **Parse** HTML content (CPU bound, also parallelizable)
3. **Aggregate** results into a report

```
    ┌────┬────┬────┬────┐
    ↓    ↓    ↓    ↓
   F0   F1   F2   F3   ← Stage 1: Parallel fetch (2s each)
    ↓    ↓    ↓    ↓
   P0   P1   P2   P3   ← Stage 2: Parallel parse (1s each)
    ↓    ↓    ↓    ↓
    └────┴────┴────┴────┘
              ↓
         Aggregate (1s)
```

## Performance

| Execution Mode | Time | Speedup |
|----------------|------|---------|
| Sequential | ~13s | 1.0x |
| Lattice Parallel | ~4s | **3.25x** |

## Requirements

**None!** Uses simulated HTTP requests (real usage would need `requests` or `aiohttp`).

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

1. **Fetches** 4 web pages in parallel (simulated):
   - Product catalog
   - Customer reviews
   - Categories
   - Trending items

2. **Parses** each page in parallel:
   - Extracts structured data
   - Computes content hash

3. **Aggregates** into a unified report:
   - Combined product list
   - Reviews by product
   - Trending items

## Real-World Applications

- **Price monitoring** - Scrape multiple e-commerce sites
- **News aggregation** - Fetch from multiple news sources
- **Data collection** - Gather data from multiple APIs
- **SEO analysis** - Check rankings across search engines
