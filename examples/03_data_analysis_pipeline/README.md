# Data Analysis Pipeline

Parallel data science workflow demonstrating concurrent analysis tasks with Lattice.

## Use Case

Run multiple independent analysis tasks (cleaning, statistics, anomaly detection, feature engineering) in parallel on the same dataset.

## Workflow

```
Load Data -> [Parallel: Clean | Stats | Anomaly | Features] -> Generate Report
```

Analysis tasks:
- **Data Cleaning**: Handle outliers and missing values
- **Statistics**: Compute descriptive statistics and correlations
- **Anomaly Detection**: Isolation Forest-based outlier detection
- **Feature Engineering**: Create derived features

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

## Dataset

Uses a synthetic e-commerce dataset with:
- Transaction data (price, quantity, revenue)
- User behavior (session duration, page views)
- Device and category information
- Intentionally injected anomalies for detection
