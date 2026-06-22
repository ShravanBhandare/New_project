import sqlite3
import pytest
from src.etl.loader import init_db

def test_init_db():
    conn = sqlite3.connect(":memory:")
    # Enable FK constraints
    conn.execute("PRAGMA foreign_keys = ON;")
    
    # Run database initialization
    # We need to read from src/etl/schema.sql, but since it is in D:/Nifty100/src/etl/schema.sql, it will find it
    import os
    # Temporarily set SCHEMA_PATH relative to workspace
    import src.etl.loader
    original_schema_path = src.etl.loader.SCHEMA_PATH
    src.etl.loader.SCHEMA_PATH = "src/etl/schema.sql"
    
    init_db(conn)
    
    # Check tables list
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [r[0] for r in cursor.fetchall()]
    
    expected_tables = [
        'companies', 'profitandloss', 'balancesheet', 'cashflow',
        'analysis', 'documents', 'prosandcons', 'sectors',
        'stock_prices', 'market_cap', 'peer_groups', 'financial_ratios'
    ]
    
    for t in expected_tables:
        assert t in tables, f"Table {t} was not created"
        
    conn.close()
