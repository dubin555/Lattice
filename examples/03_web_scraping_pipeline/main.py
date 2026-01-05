"""
Web Scraping Pipeline - Demonstrates Multi-Stage Parallel Processing
=====================================================================

This example shows how Lattice can accelerate web scraping workflows
by parallelizing both the fetching and processing stages.

Workflow Structure:
    URL List Input
         ↓
    ┌────┬────┬────┐
    ↓    ↓    ↓    ↓
  Fetch Fetch Fetch Fetch  ← Stage 1: Parallel fetching (2s each)
    ↓    ↓    ↓    ↓
    └────┴────┴────┘
         ↓
    ┌────┬────┬────┐
    ↓    ↓    ↓    ↓
 Parse Parse Parse Parse   ← Stage 2: Parallel parsing (1s each)
    ↓    ↓    ↓    ↓
    └────┴────┴────┘
         ↓
    Aggregate & Report

Performance:
    - Sequential: 4×2 + 4×1 + 1 = 13 seconds
    - Lattice Parallel: 2 + 1 + 1 = 4 seconds (3.25x speedup)

Requirements: None (simulates HTTP requests with time.sleep)

Usage:
    1. Start Lattice server: lattice start --head --port 8000
    2. Run this script: python main.py
"""

import time
import random
import hashlib
from lattice import LatticeClient, task


MOCK_WEB_CONTENT = {
    "https://example.com/products": {
        "title": "Product Catalog",
        "items": [
            {"name": "Widget A", "price": 29.99, "stock": 150},
            {"name": "Widget B", "price": 49.99, "stock": 75},
            {"name": "Widget C", "price": 19.99, "stock": 200},
        ]
    },
    "https://example.com/reviews": {
        "title": "Customer Reviews",
        "reviews": [
            {"product": "Widget A", "rating": 4.5, "count": 128},
            {"product": "Widget B", "rating": 4.8, "count": 64},
            {"product": "Widget C", "rating": 4.2, "count": 256},
        ]
    },
    "https://example.com/categories": {
        "title": "Categories",
        "categories": [
            {"name": "Electronics", "products": 45},
            {"name": "Home & Garden", "products": 32},
            {"name": "Sports", "products": 28},
        ]
    },
    "https://example.com/trending": {
        "title": "Trending Now",
        "trending": [
            {"product": "Widget B", "rank": 1, "sales_increase": "45%"},
            {"product": "Widget A", "rank": 2, "sales_increase": "23%"},
            {"product": "Widget C", "rank": 3, "sales_increase": "12%"},
        ]
    },
}


@task(
    inputs=["url"],
    outputs=["raw_html", "fetch_time", "status_code"],
    resources={"cpu": 1, "cpu_mem": 256}
)
def fetch_page(params):
    """
    Fetch a web page (simulated).
    In real usage, this would use requests/aiohttp.
    """
    url = params.get("url")
    print(f"[Fetch] Fetching: {url}")
    
    time.sleep(2 + random.uniform(0, 0.5))
    
    content = MOCK_WEB_CONTENT.get(url, {"error": "Not found"})
    
    raw_html = f"<html><body>{content}</body></html>"
    
    print(f"[Fetch] ✓ Fetched: {url} ({len(raw_html)} bytes)")
    
    return {
        "raw_html": raw_html,
        "fetch_time": time.time(),
        "status_code": 200
    }


@task(
    inputs=["url", "raw_html"],
    outputs=["parsed_data", "parse_time"],
    resources={"cpu": 1, "cpu_mem": 256}
)
def parse_content(params):
    """
    Parse and extract structured data from HTML.
    """
    url = params.get("url")
    raw_html = params.get("raw_html")
    
    print(f"[Parse] Parsing content from: {url}")
    
    time.sleep(1 + random.uniform(0, 0.3))
    
    content = MOCK_WEB_CONTENT.get(url, {})
    
    parsed = {
        "url": url,
        "title": content.get("title", "Unknown"),
        "content_hash": hashlib.md5(raw_html.encode()).hexdigest()[:8],
        "data": content,
    }
    
    print(f"[Parse] ✓ Parsed: {parsed['title']}")
    
    return {
        "parsed_data": parsed,
        "parse_time": time.time()
    }


@task(
    inputs=["parsed_data_0", "parsed_data_1", "parsed_data_2", "parsed_data_3"],
    outputs=["report"],
    resources={"cpu": 1, "cpu_mem": 256}
)
def aggregate_data(params):
    """
    Aggregate all parsed data into a unified report.
    """
    print(f"[Aggregate] Combining data from all sources...")
    
    all_data = [
        params.get("parsed_data_0"),
        params.get("parsed_data_1"),
        params.get("parsed_data_2"),
        params.get("parsed_data_3"),
    ]
    
    time.sleep(1)
    
    products = []
    for data in all_data:
        if data and "items" in data.get("data", {}):
            products.extend(data["data"]["items"])
    
    reviews = {}
    for data in all_data:
        if data and "reviews" in data.get("data", {}):
            for review in data["data"]["reviews"]:
                reviews[review["product"]] = review
    
    trending = []
    for data in all_data:
        if data and "trending" in data.get("data", {}):
            trending = data["data"]["trending"]
    
    report = {
        "pages_scraped": len(all_data),
        "products_found": len(products),
        "products": products,
        "reviews": reviews,
        "trending": trending,
        "sources": [d["url"] for d in all_data if d],
    }
    
    print(f"[Aggregate] ✓ Report generated: {len(products)} products, {len(reviews)} reviews")
    
    return {"report": report}


def main():
    print("=" * 60)
    print("🌐 Lattice Web Scraping Pipeline Demo")
    print("=" * 60)
    print("""
This demo shows how Lattice parallelizes a web scraping workflow
with multiple stages: fetch → parse → aggregate.

All fetches happen in parallel, then all parsing happens in parallel.
    """)
    
    urls = [
        "https://example.com/products",
        "https://example.com/reviews",
        "https://example.com/categories",
        "https://example.com/trending",
    ]
    
    print(f"\n📋 URLs to scrape: {len(urls)}")
    for url in urls:
        print(f"   - {url}")
    
    print("\n" + "=" * 60)
    print("Running with LATTICE parallel execution...")
    print("=" * 60)
    
    start_time = time.time()
    
    client = LatticeClient("http://localhost:8000")
    workflow = client.create_workflow()
    
    fetch_tasks = []
    for i, url in enumerate(urls):
        fetch_task = workflow.add_task(
            fetch_page,
            inputs={"url": url},
            task_name=f"fetch_{i}"
        )
        fetch_tasks.append(fetch_task)
    
    parse_tasks = []
    for i, (url, fetch_task) in enumerate(zip(urls, fetch_tasks)):
        parse_task = workflow.add_task(
            parse_content,
            inputs={
                "url": url,
                "raw_html": fetch_task.outputs["raw_html"]
            },
            task_name=f"parse_{i}"
        )
        parse_tasks.append(parse_task)
    
    aggregate_task = workflow.add_task(
        aggregate_data,
        inputs={
            "parsed_data_0": parse_tasks[0].outputs["parsed_data"],
            "parsed_data_1": parse_tasks[1].outputs["parsed_data"],
            "parsed_data_2": parse_tasks[2].outputs["parsed_data"],
            "parsed_data_3": parse_tasks[3].outputs["parsed_data"],
        }
    )
    
    print("\n📊 Workflow Structure:")
    print("    ┌────┬────┬────┬────┐")
    print("    ↓    ↓    ↓    ↓")
    print("   F0   F1   F2   F3   ← Parallel fetch")
    print("    ↓    ↓    ↓    ↓")
    print("   P0   P1   P2   P3   ← Parallel parse")
    print("    ↓    ↓    ↓    ↓")
    print("    └────┴────┴────┴────┘")
    print("              ↓")
    print("         Aggregate")
    print()
    
    run_id = workflow.run()
    results = workflow.get_results(run_id, verbose=False)
    
    elapsed = time.time() - start_time
    
    for msg in results:
        if msg.get("type") == "task_complete":
            output = msg.get("output", {})
            if "report" in output:
                report = output["report"]
                print("\n📋 Scraping Report:")
                print(f"   Pages Scraped: {report['pages_scraped']}")
                print(f"   Products Found: {report['products_found']}")
                print("\n   Products:")
                for p in report.get('products', []):
                    print(f"      - {p['name']}: ${p['price']} ({p['stock']} in stock)")
                print("\n   Trending:")
                for t in report.get('trending', []):
                    print(f"      #{t['rank']} {t['product']} (+{t['sales_increase']})")
    
    print(f"\n[Lattice] Total time: {elapsed:.1f} seconds")
    
    print("\n" + "=" * 60)
    print("📈 PERFORMANCE COMPARISON")
    print("=" * 60)
    sequential_time = 4 * 2 + 4 * 1 + 1
    print(f"""
Sequential execution (baseline): ~{sequential_time} seconds
Lattice parallel execution:      ~{elapsed:.1f} seconds

Speedup: {sequential_time / elapsed:.1f}x faster!

In real-world scraping with network latency, the parallel advantage
is even more pronounced since I/O wait time dominates.
""")


if __name__ == "__main__":
    main()
