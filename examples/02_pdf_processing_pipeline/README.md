# PDF Processing Pipeline

Enterprise document analysis example demonstrating parallel PDF processing with Lattice.

## Use Case

Process multiple PDF documents in parallel, extracting text and performing various analyses (keyword extraction, statistics, summarization) concurrently.

## Workflow

```
PDFs -> [Parallel Text Extraction] -> [Parallel Analysis Tasks] -> Generate Report
```

Analysis tasks include:
- Keyword extraction (TF-based)
- Text statistics
- Extractive summarization

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

## Notes

This example uses simulated PDF content to avoid requiring actual PDF files. In production, you would use `pypdf` or similar libraries to extract text from real PDFs.
