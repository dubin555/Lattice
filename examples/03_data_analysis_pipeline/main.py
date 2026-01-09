"""
Data Analysis Pipeline - Parallel Feature Engineering & Analysis
=================================================================

A practical data science example showing parallel execution of
independent analysis tasks on a dataset.

Workflow Structure:
    Raw Data (CSV)
         |
    Task A: Data Loading & Validation
         |
    +----+----+----+----+
    |    |    |    |    |
  Clean Stats Anomaly Features   <- Parallel analysis
    |    |    |    |    |
    +----+----+----+----+
         |
    Task B: Generate Analysis Report

This pattern is common in data pipelines where multiple independent
analyses can run concurrently on the same dataset.

Requirements: pandas, numpy, scikit-learn

Usage:
    1. Start Lattice server: lattice start --head --port 8000
    2. Install deps: pip install pandas numpy scikit-learn
    3. Run: python main.py
"""

import time
import numpy as np
import pandas as pd
from typing import Dict, Any, List
from lattice import LatticeClient, task


def generate_sample_dataset(n_samples: int = 1000) -> pd.DataFrame:
    """Generate a sample e-commerce dataset for analysis."""
    np.random.seed(42)
    
    dates = pd.date_range(start='2024-01-01', periods=n_samples, freq='h')
    
    data = {
        'timestamp': dates,
        'user_id': np.random.randint(1, 500, n_samples),
        'product_id': np.random.randint(1, 100, n_samples),
        'category': np.random.choice(['electronics', 'clothing', 'home', 'sports', 'books'], n_samples),
        'price': np.random.lognormal(mean=3.5, sigma=0.8, size=n_samples).round(2),
        'quantity': np.random.randint(1, 5, n_samples),
        'session_duration': np.random.exponential(scale=300, size=n_samples).round(0),
        'page_views': np.random.poisson(lam=8, size=n_samples),
        'is_returning': np.random.choice([0, 1], n_samples, p=[0.4, 0.6]),
        'device': np.random.choice(['mobile', 'desktop', 'tablet'], n_samples, p=[0.5, 0.35, 0.15]),
    }
    
    anomaly_indices = np.random.choice(n_samples, size=int(n_samples * 0.02), replace=False)
    data['price'][anomaly_indices] = data['price'][anomaly_indices] * 10
    data['session_duration'][anomaly_indices] = data['session_duration'][anomaly_indices] * 5
    
    df = pd.DataFrame(data)
    df['revenue'] = df['price'] * df['quantity']
    
    return df


@task(
    inputs=["data_dict"],
    outputs=["validated_data", "validation_report"],
    resources={"cpu": 1, "cpu_mem": 512}
)
def load_and_validate_data(params: Dict[str, Any]) -> Dict[str, Any]:
    """Load data and perform basic validation."""
    data_dict = params.get("data_dict", {})
    
    print(f"[Load] Loading and validating data...")
    
    df = pd.DataFrame(data_dict)
    
    report = {
        "rows": len(df),
        "columns": len(df.columns),
        "missing_values": df.isnull().sum().to_dict(),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
    }
    
    print(f"[Load] Validated {report['rows']} rows, {report['columns']} columns")
    
    return {
        "validated_data": df.to_dict('list'),
        "validation_report": report,
    }


@task(
    inputs=["data_dict"],
    outputs=["cleaned_data", "cleaning_report"],
    resources={"cpu": 2, "cpu_mem": 1024}
)
def clean_data(params: Dict[str, Any]) -> Dict[str, Any]:
    """Clean data: handle missing values, outliers, data types."""
    data_dict = params.get("data_dict", {})
    
    print(f"[Clean] Cleaning data...")
    
    df = pd.DataFrame(data_dict)
    original_rows = len(df)
    
    df = df.dropna()
    
    for col in ['price', 'revenue', 'session_duration']:
        if col in df.columns:
            q1, q3 = df[col].quantile([0.01, 0.99])
            df = df[(df[col] >= q1) & (df[col] <= q3)]
    
    cleaning_report = {
        "original_rows": original_rows,
        "cleaned_rows": len(df),
        "rows_removed": original_rows - len(df),
        "removal_percentage": round((original_rows - len(df)) / original_rows * 100, 2),
    }
    
    print(f"[Clean] Removed {cleaning_report['rows_removed']} rows ({cleaning_report['removal_percentage']}%)")
    
    return {
        "cleaned_data": df.to_dict('list'),
        "cleaning_report": cleaning_report,
    }


@task(
    inputs=["data_dict"],
    outputs=["statistics"],
    resources={"cpu": 2, "cpu_mem": 1024}
)
def compute_statistics(params: Dict[str, Any]) -> Dict[str, Any]:
    """Compute comprehensive statistical analysis."""
    data_dict = params.get("data_dict", {})
    
    print(f"[Stats] Computing statistics...")
    
    df = pd.DataFrame(data_dict)
    
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    
    stats = {
        "summary": {},
        "correlations": {},
        "category_analysis": {},
    }
    
    for col in numeric_cols:
        if col not in ['user_id', 'product_id']:
            stats["summary"][col] = {
                "mean": round(df[col].mean(), 2),
                "std": round(df[col].std(), 2),
                "min": round(df[col].min(), 2),
                "max": round(df[col].max(), 2),
                "median": round(df[col].median(), 2),
            }
    
    if 'revenue' in df.columns and 'session_duration' in df.columns:
        stats["correlations"]["revenue_session"] = round(
            df['revenue'].corr(df['session_duration']), 3
        )
    if 'page_views' in df.columns and 'revenue' in df.columns:
        stats["correlations"]["pageviews_revenue"] = round(
            df['page_views'].corr(df['revenue']), 3
        )
    
    if 'category' in df.columns and 'revenue' in df.columns:
        category_stats = df.groupby('category')['revenue'].agg(['mean', 'sum', 'count'])
        stats["category_analysis"] = category_stats.round(2).to_dict()
    
    print(f"[Stats] Computed statistics for {len(stats['summary'])} numeric columns")
    
    return {"statistics": stats}


@task(
    inputs=["data_dict", "contamination"],
    outputs=["anomalies", "anomaly_report"],
    resources={"cpu": 2, "cpu_mem": 1024}
)
def detect_anomalies(params: Dict[str, Any]) -> Dict[str, Any]:
    """Detect anomalies using Isolation Forest."""
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    
    data_dict = params.get("data_dict", {})
    contamination = params.get("contamination", 0.05)
    
    print(f"[Anomaly] Detecting anomalies...")
    
    df = pd.DataFrame(data_dict)
    
    feature_cols = ['price', 'quantity', 'session_duration', 'page_views', 'revenue']
    feature_cols = [c for c in feature_cols if c in df.columns]
    
    X = df[feature_cols].values
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    iso_forest = IsolationForest(contamination=contamination, random_state=42, n_jobs=-1)
    predictions = iso_forest.fit_predict(X_scaled)
    
    anomaly_mask = predictions == -1
    anomaly_indices = np.where(anomaly_mask)[0].tolist()
    
    report = {
        "total_samples": len(df),
        "anomalies_detected": int(anomaly_mask.sum()),
        "anomaly_percentage": round(anomaly_mask.mean() * 100, 2),
        "features_used": feature_cols,
    }
    
    print(f"[Anomaly] Detected {report['anomalies_detected']} anomalies ({report['anomaly_percentage']}%)")
    
    return {
        "anomalies": anomaly_indices[:20],
        "anomaly_report": report,
    }


@task(
    inputs=["data_dict"],
    outputs=["features", "feature_report"],
    resources={"cpu": 2, "cpu_mem": 1024}
)
def engineer_features(params: Dict[str, Any]) -> Dict[str, Any]:
    """Create derived features for machine learning."""
    data_dict = params.get("data_dict", {})
    
    print(f"[Features] Engineering features...")
    
    df = pd.DataFrame(data_dict)
    
    new_features = {}
    
    if 'revenue' in df.columns and 'quantity' in df.columns:
        new_features['avg_item_price'] = (df['revenue'] / df['quantity']).round(2).tolist()
    
    if 'page_views' in df.columns and 'session_duration' in df.columns:
        new_features['pages_per_minute'] = (
            df['page_views'] / (df['session_duration'] / 60 + 0.1)
        ).round(2).tolist()
    
    if 'session_duration' in df.columns:
        duration_bins = pd.qcut(df['session_duration'], q=4, labels=['short', 'medium', 'long', 'very_long'])
        new_features['session_bucket'] = duration_bins.astype(str).tolist()
    
    if 'price' in df.columns:
        price_bins = pd.qcut(df['price'], q=3, labels=['low', 'medium', 'high'])
        new_features['price_tier'] = price_bins.astype(str).tolist()
    
    if 'is_returning' in df.columns and 'revenue' in df.columns:
        avg_revenue = df.groupby('is_returning')['revenue'].transform('mean')
        new_features['revenue_vs_avg'] = (df['revenue'] / avg_revenue).round(2).tolist()
    
    report = {
        "features_created": list(new_features.keys()),
        "feature_count": len(new_features),
    }
    
    print(f"[Features] Created {report['feature_count']} new features")
    
    return {
        "features": new_features,
        "feature_report": report,
    }


@task(
    inputs=["validation_report", "cleaning_report", "statistics", "anomaly_report", "feature_report"],
    outputs=["final_report"],
    resources={"cpu": 1, "cpu_mem": 256}
)
def generate_report(params: Dict[str, Any]) -> Dict[str, Any]:
    """Generate comprehensive analysis report."""
    print(f"[Report] Generating final report...")
    
    report = {
        "data_validation": params.get("validation_report", {}),
        "data_cleaning": params.get("cleaning_report", {}),
        "statistical_analysis": params.get("statistics", {}),
        "anomaly_detection": params.get("anomaly_report", {}),
        "feature_engineering": params.get("feature_report", {}),
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    
    print(f"[Report] Final report generated with {len(report)} sections")
    
    return {"final_report": report}


def main():
    print("=" * 65)
    print("Data Analysis Pipeline - Parallel Processing with Lattice")
    print("=" * 65)
    
    print("\nGenerating sample e-commerce dataset...")
    df = generate_sample_dataset(n_samples=2000)
    print(f"  - Rows: {len(df)}")
    print(f"  - Columns: {list(df.columns)}")
    print(f"  - Total Revenue: ${df['revenue'].sum():,.2f}")
    
    data_dict = df.to_dict('list')
    
    start_time = time.time()
    
    client = LatticeClient("http://localhost:8000")
    workflow = client.create_workflow()
    
    load_task = workflow.add_task(
        load_and_validate_data,
        inputs={"data_dict": data_dict}
    )
    
    clean_task = workflow.add_task(
        clean_data,
        inputs={"data_dict": load_task.outputs["validated_data"]}
    )
    
    stats_task = workflow.add_task(
        compute_statistics,
        inputs={"data_dict": load_task.outputs["validated_data"]}
    )
    
    anomaly_task = workflow.add_task(
        detect_anomalies,
        inputs={
            "data_dict": load_task.outputs["validated_data"],
            "contamination": 0.05,
        }
    )
    
    feature_task = workflow.add_task(
        engineer_features,
        inputs={"data_dict": load_task.outputs["validated_data"]}
    )
    
    report_task = workflow.add_task(
        generate_report,
        inputs={
            "validation_report": load_task.outputs["validation_report"],
            "cleaning_report": clean_task.outputs["cleaning_report"],
            "statistics": stats_task.outputs["statistics"],
            "anomaly_report": anomaly_task.outputs["anomaly_report"],
            "feature_report": feature_task.outputs["feature_report"],
        }
    )
    
    print("\nWorkflow Structure:")
    print("         Load & Validate")
    print("              |")
    print("    +---------+---------+")
    print("    |    |    |    |")
    print("  Clean Stats Anom Feat  <- Parallel analysis")
    print("    |    |    |    |")
    print("    +---------+---------+")
    print("              |")
    print("       Generate Report")
    print()
    
    run_id = workflow.run()
    results = workflow.get_results(run_id, verbose=False)
    
    elapsed = time.time() - start_time
    
    for msg in results:
        if msg.get("type") == "task_complete":
            output = msg.get("output", {})
            if "final_report" in output:
                report = output["final_report"]
                
                print("\n" + "=" * 50)
                print("ANALYSIS REPORT")
                print("=" * 50)
                
                cleaning = report.get("data_cleaning", {})
                print(f"\nData Cleaning:")
                print(f"  - Rows removed: {cleaning.get('rows_removed', 'N/A')}")
                print(f"  - Removal rate: {cleaning.get('removal_percentage', 'N/A')}%")
                
                stats = report.get("statistical_analysis", {})
                if "summary" in stats and "revenue" in stats["summary"]:
                    rev = stats["summary"]["revenue"]
                    print(f"\nRevenue Statistics:")
                    print(f"  - Mean: ${rev.get('mean', 0):,.2f}")
                    print(f"  - Median: ${rev.get('median', 0):,.2f}")
                    print(f"  - Std Dev: ${rev.get('std', 0):,.2f}")
                
                anomaly = report.get("anomaly_detection", {})
                print(f"\nAnomaly Detection:")
                print(f"  - Anomalies found: {anomaly.get('anomalies_detected', 'N/A')}")
                print(f"  - Percentage: {anomaly.get('anomaly_percentage', 'N/A')}%")
                
                features = report.get("feature_engineering", {})
                print(f"\nFeature Engineering:")
                print(f"  - Features created: {features.get('feature_count', 'N/A')}")
                print(f"  - Names: {', '.join(features.get('features_created', []))}")
    
    print(f"\nTotal pipeline time: {elapsed:.2f} seconds")
    print("\nThis pipeline demonstrates parallel data analysis tasks,")
    print("a common pattern in data science workflows.")


if __name__ == "__main__":
    main()
