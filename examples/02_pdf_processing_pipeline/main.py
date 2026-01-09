"""
PDF Processing Pipeline - Enterprise Document Analysis
=======================================================

A practical example showing parallel PDF document processing:
text extraction, keyword analysis, and summarization.

Workflow Structure:
    PDF Files
         |
    +----+----+----+
    |    |    |    |
  Extract Extract Extract Extract  <- Parallel text extraction
    |    |    |    |
    +----+----+----+
         |
    +----+----+----+
    |    |    |    |
Keywords Stats Summary TF-IDF     <- Parallel analysis
    |    |    |    |
    +----+----+----+
         |
    Generate Report

This pattern is common in document processing pipelines where
multiple analysis tasks can run independently on extracted text.

Requirements: pypdf, nltk

Usage:
    1. Start Lattice server: lattice start --head --port 8000
    2. Install deps: pip install pypdf nltk
    3. Run: python main.py
"""

import time
import os
import re
from collections import Counter
from typing import Dict, Any, List
from lattice import LatticeClient, task

SAMPLE_TEXTS = [
    {
        "filename": "quarterly_report_q1.pdf",
        "content": """Quarterly Financial Report Q1 2024
        
        Executive Summary: The company achieved record revenue of $50 million in Q1, 
        representing a 25% year-over-year growth. Operating margins improved to 18%, 
        driven by cost optimization initiatives and increased operational efficiency.
        
        Key Highlights:
        - Revenue: $50M (up 25% YoY)
        - Gross Margin: 45%
        - Operating Income: $9M
        - New Customers: 150
        - Customer Retention: 95%
        
        Market Analysis: The technology sector showed strong growth momentum with 
        increasing demand for cloud-based solutions. Our SaaS platform gained significant 
        traction in the enterprise segment, with several Fortune 500 companies joining 
        as new customers.
        
        Outlook: We expect continued growth in Q2 with projected revenue of $55M."""
    },
    {
        "filename": "product_roadmap.pdf",
        "content": """Product Roadmap 2024
        
        Vision: Transform enterprise workflows through intelligent automation and 
        AI-powered insights.
        
        Q1 Deliverables (Completed):
        - Machine learning pipeline optimization
        - Real-time analytics dashboard
        - Enhanced security features
        
        Q2 Priorities:
        - Natural language query interface
        - Advanced reporting capabilities  
        - Mobile application launch
        - API rate limiting improvements
        
        Q3-Q4 Initiatives:
        - Multi-cloud deployment support
        - Predictive analytics module
        - Enterprise SSO integration
        - Performance optimization phase 2
        
        Technical Debt:
        - Database migration to PostgreSQL 15
        - Legacy API deprecation
        - Infrastructure modernization"""
    },
    {
        "filename": "research_paper.pdf",
        "content": """Advances in Distributed Computing for Large Language Models
        
        Abstract: This paper presents a novel approach to distributed task scheduling 
        for LLM inference workloads. We demonstrate significant latency improvements 
        through intelligent workload distribution across heterogeneous compute clusters.
        
        Introduction: Large language models require substantial computational resources 
        for both training and inference. Traditional approaches often underutilize 
        available resources due to inefficient scheduling algorithms.
        
        Methodology: We propose a task-level parallelism framework that automatically 
        identifies independent operations within LLM workflows and distributes them 
        across available compute nodes. Our scheduler considers factors including 
        memory requirements, compute intensity, and network bandwidth.
        
        Results: Experiments show 3.2x throughput improvement on multi-node clusters 
        compared to baseline sequential execution. Memory utilization improved by 40%.
        
        Conclusion: Task-level parallelism offers significant performance benefits 
        for LLM workloads with minimal changes to existing inference pipelines."""
    },
    {
        "filename": "employee_handbook.pdf",
        "content": """Employee Handbook 2024 Edition
        
        Welcome: We are thrilled to have you join our team. This handbook provides 
        essential information about company policies, benefits, and workplace culture.
        
        Core Values:
        - Innovation: We encourage creative problem-solving
        - Integrity: We maintain highest ethical standards
        - Collaboration: We work together to achieve goals
        - Excellence: We strive for quality in everything
        
        Benefits Overview:
        - Health insurance (medical, dental, vision)
        - 401(k) with 4% company match
        - Flexible PTO policy
        - Remote work options
        - Professional development budget
        
        Work Environment: We maintain a hybrid work model with Tuesday and Thursday 
        as in-office collaboration days. Remote work is available for other days.
        
        Performance Reviews: Annual reviews conducted in December with mid-year 
        check-ins in June."""
    },
]


@task(
    inputs=["pdf_data"],
    outputs=["extracted_text", "metadata"],
    resources={"cpu": 1, "cpu_mem": 512}
)
def extract_text_from_pdf(params: Dict[str, Any]) -> Dict[str, Any]:
    """Extract text content from PDF (simulated with sample text)."""
    pdf_data = params.get("pdf_data", {})
    filename = pdf_data.get("filename", "unknown.pdf")
    
    print(f"[Extract] Processing: {filename}")
    
    time.sleep(0.5)
    
    text = pdf_data.get("content", "")
    
    metadata = {
        "filename": filename,
        "char_count": len(text),
        "word_count": len(text.split()),
        "line_count": len(text.split("\n")),
    }
    
    print(f"[Extract] Extracted {metadata['word_count']} words from {filename}")
    
    return {
        "extracted_text": text,
        "metadata": metadata,
    }


@task(
    inputs=["text", "top_n"],
    outputs=["keywords"],
    resources={"cpu": 1, "cpu_mem": 512}
)
def extract_keywords(params: Dict[str, Any]) -> Dict[str, Any]:
    """Extract keywords using frequency analysis."""
    import nltk
    try:
        nltk.data.find('corpora/stopwords')
    except LookupError:
        nltk.download('stopwords', quiet=True)
    
    from nltk.corpus import stopwords
    
    text = params.get("text", "")
    top_n = params.get("top_n", 10)
    
    print(f"[Keywords] Analyzing text ({len(text)} chars)...")
    
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    stop_words = set(stopwords.words('english'))
    
    filtered_words = [w for w in words if w not in stop_words]
    word_freq = Counter(filtered_words)
    
    keywords = [
        {"word": word, "count": count}
        for word, count in word_freq.most_common(top_n)
    ]
    
    print(f"[Keywords] Found top {len(keywords)} keywords")
    
    return {"keywords": keywords}


@task(
    inputs=["text"],
    outputs=["statistics"],
    resources={"cpu": 1, "cpu_mem": 256}
)
def compute_text_statistics(params: Dict[str, Any]) -> Dict[str, Any]:
    """Compute various text statistics."""
    text = params.get("text", "")
    
    print(f"[Stats] Computing statistics...")
    
    words = text.split()
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    word_lengths = [len(w) for w in words]
    avg_word_length = sum(word_lengths) / len(word_lengths) if word_lengths else 0
    avg_sentence_length = len(words) / len(sentences) if sentences else 0
    
    unique_words = set(w.lower() for w in words)
    lexical_diversity = len(unique_words) / len(words) if words else 0
    
    stats = {
        "total_words": len(words),
        "unique_words": len(unique_words),
        "total_sentences": len(sentences),
        "avg_word_length": round(avg_word_length, 2),
        "avg_sentence_length": round(avg_sentence_length, 2),
        "lexical_diversity": round(lexical_diversity, 3),
    }
    
    print(f"[Stats] Computed: {stats['total_words']} words, {stats['total_sentences']} sentences")
    
    return {"statistics": stats}


@task(
    inputs=["text", "max_sentences"],
    outputs=["summary"],
    resources={"cpu": 1, "cpu_mem": 512}
)
def generate_extractive_summary(params: Dict[str, Any]) -> Dict[str, Any]:
    """Generate extractive summary by selecting key sentences."""
    text = params.get("text", "")
    max_sentences = params.get("max_sentences", 3)
    
    print(f"[Summary] Generating summary...")
    
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 20]
    
    scored_sentences = []
    for sent in sentences:
        words = sent.lower().split()
        important_words = ['revenue', 'growth', 'key', 'important', 'results', 
                          'conclusion', 'summary', 'achieved', 'improved', 'significant']
        score = sum(1 for w in words if w in important_words)
        score += len(words) / 50
        if sent == sentences[0]:
            score += 2
        scored_sentences.append((score, sent))
    
    scored_sentences.sort(reverse=True)
    top_sentences = [s[1] for s in scored_sentences[:max_sentences]]
    
    summary = ". ".join(top_sentences)
    if not summary.endswith("."):
        summary += "."
    
    print(f"[Summary] Generated {len(top_sentences)}-sentence summary")
    
    return {"summary": summary}


@task(
    inputs=["keywords", "statistics", "summary", "metadata_list"],
    outputs=["report"],
    resources={"cpu": 1, "cpu_mem": 256}
)
def generate_analysis_report(params: Dict[str, Any]) -> Dict[str, Any]:
    """Generate final analysis report combining all results."""
    keywords = params.get("keywords", [])
    statistics = params.get("statistics", {})
    summary = params.get("summary", "")
    metadata_list = params.get("metadata_list", [])
    
    print(f"[Report] Generating final report...")
    
    report = {
        "documents_analyzed": len(metadata_list),
        "total_words_processed": sum(m.get("word_count", 0) for m in metadata_list),
        "files": [m.get("filename", "unknown") for m in metadata_list],
        "top_keywords": keywords[:5] if keywords else [],
        "text_statistics": statistics,
        "executive_summary": summary,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    
    print(f"[Report] Report complete: {report['documents_analyzed']} documents analyzed")
    
    return {"report": report}


def main():
    print("=" * 65)
    print("PDF Processing Pipeline - Document Analysis with Lattice")
    print("=" * 65)
    
    print(f"\nDocuments to process: {len(SAMPLE_TEXTS)}")
    for doc in SAMPLE_TEXTS:
        print(f"  - {doc['filename']}")
    
    start_time = time.time()
    
    client = LatticeClient("http://localhost:8000")
    workflow = client.create_workflow()
    
    extract_tasks = []
    for i, pdf_data in enumerate(SAMPLE_TEXTS):
        extract_task = workflow.add_task(
            extract_text_from_pdf,
            inputs={"pdf_data": pdf_data},
            task_name=f"extract_{i}"
        )
        extract_tasks.append(extract_task)
    
    all_text = " ".join([doc["content"] for doc in SAMPLE_TEXTS])
    all_metadata = [{"filename": doc["filename"], "word_count": len(doc["content"].split())} 
                    for doc in SAMPLE_TEXTS]
    
    keyword_task = workflow.add_task(
        extract_keywords,
        inputs={
            "text": all_text,
            "top_n": 15,
        }
    )
    
    stats_task = workflow.add_task(
        compute_text_statistics,
        inputs={"text": all_text}
    )
    
    summary_task = workflow.add_task(
        generate_extractive_summary,
        inputs={
            "text": all_text,
            "max_sentences": 4,
        }
    )
    
    report_task = workflow.add_task(
        generate_analysis_report,
        inputs={
            "keywords": keyword_task.outputs["keywords"],
            "statistics": stats_task.outputs["statistics"],
            "summary": summary_task.outputs["summary"],
            "metadata_list": all_metadata,
        }
    )
    
    print("\nWorkflow Structure:")
    print("    +------+------+------+------+")
    print("    |      |      |      |      |")
    print("  PDF1   PDF2   PDF3   PDF4    <- Parallel extraction")
    print("    |      |      |      |      |")
    print("    +------+------+------+------+")
    print("              |")
    print("    +----+----+----+")
    print("    |    |    |")
    print("  Keys Stats  Sum    <- Parallel analysis")
    print("    |    |    |")
    print("    +----+----+----+")
    print("         |")
    print("    Final Report")
    print()
    
    run_id = workflow.run()
    results = workflow.get_results(run_id, verbose=False)
    
    elapsed = time.time() - start_time
    
    for msg in results:
        if msg.get("type") == "task_complete":
            output = msg.get("output", {})
            if "report" in output:
                report = output["report"]
                print("\nAnalysis Report:")
                print(f"  Documents: {report.get('documents_analyzed', 'N/A')}")
                print(f"  Words Processed: {report.get('total_words_processed', 'N/A')}")
                print(f"\n  Top Keywords:")
                for kw in report.get('top_keywords', []):
                    print(f"    - {kw['word']}: {kw['count']} occurrences")
                stats = report.get('text_statistics', {})
                print(f"\n  Statistics:")
                print(f"    - Unique Words: {stats.get('unique_words', 'N/A')}")
                print(f"    - Lexical Diversity: {stats.get('lexical_diversity', 'N/A')}")
                print(f"\n  Summary: {report.get('executive_summary', 'N/A')[:200]}...")
    
    print(f"\nTotal pipeline time: {elapsed:.2f} seconds")


if __name__ == "__main__":
    main()
