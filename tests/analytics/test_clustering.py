import os
import sqlite3
import pandas as pd
import pytest
from src.analytics.clustering import run_clustering_and_analytics

DB_PATH = "data/nifty100.db"

def test_run_clustering_generates_outputs():
    # Make sure execution doesn't raise error
    run_clustering_and_analytics()
    
    # Assert output files exist
    assert os.path.exists("output/clustering_results.csv")
    assert os.path.exists("output/correlation_matrix.csv")
    assert os.path.exists("output/sector_outliers.csv")
    assert os.path.exists("output/nifty100_percentiles.csv")

def test_clustering_database_table():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='company_clusters'")
    table_exists = cursor.fetchone()
    assert table_exists is not None
    
    # Check record count
    cursor.execute("SELECT COUNT(*) FROM company_clusters")
    count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(DISTINCT company_id) FROM financial_ratios")
    ratios_comp_count = cursor.fetchone()[0]
    assert count == ratios_comp_count
    
    # Check columns
    cursor.execute("PRAGMA table_info(company_clusters)")
    cols = [col[1] for col in cursor.fetchall()]
    assert "company_id" in cols
    assert "cluster_id" in cols
    assert "cluster_name" in cols
    assert "cluster_description" in cols
    
    conn.close()

def test_correlation_matrix_values():
    df = pd.read_csv("output/correlation_matrix.csv", index_index=0) if 'index_index' in pd.read_csv("output/correlation_matrix.csv").columns else pd.read_csv("output/correlation_matrix.csv", index_col=0)
    assert df.shape == (10, 10)
    # Diagonal values should be 1.0 (or very close due to float rounding)
    for col in df.columns:
        assert abs(df.loc[col, col] - 1.0) < 1e-5

def test_sector_outliers_structure():
    df = pd.read_csv("output/sector_outliers.csv")
    if not df.empty:
        assert "company_id" in df.columns
        assert "kpi" in df.columns
        assert "z_score" in df.columns
        # Z-scores absolute value should be > 3.0
        for val in df['z_score']:
            assert abs(val) > 3.0

def test_percentiles_range():
    df = pd.read_csv("output/nifty100_percentiles.csv", index_col=0)
    assert df.shape[0] == 10  # 10 KPIs
    assert "P10" in df.columns
    assert "P90" in df.columns
    # P10 should be less than or equal to P90
    for idx, row in df.iterrows():
        assert row["P10"] <= row["P90"]
