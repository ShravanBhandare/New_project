import sqlite3
import pandas as pd
from typing import Dict, Any, List

DB_PATH = "data/nifty100.db"

def get_connection() -> sqlite3.Connection:
    """Return a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def get_companies() -> pd.DataFrame:
    """Fetch list of all 92 companies with their sector and key metrics."""
    conn = get_connection()
    query = """
    SELECT c.id, c.company_name, s.broad_sector, s.sub_sector
    FROM companies c
    JOIN sectors s ON c.id = s.company_id
    ORDER BY c.id
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def get_company_details(ticker: str) -> Dict[str, Any]:
    """Fetch basic info, logos, descriptions, websites, and multiples for a company."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Fetch info from companies and sectors
    query = """
    SELECT c.*, s.broad_sector, s.sub_sector, s.index_weight_pct, s.market_cap_category
    FROM companies c
    JOIN sectors s ON c.id = s.company_id
    WHERE c.id = ?
    """
    cursor.execute(query, (ticker,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {}
        
    colnames = [desc[0] for desc in cursor.description]
    comp_info = dict(zip(colnames, row))
    
    # 2. Fetch latest multiples from market_cap
    cursor.execute("SELECT * FROM market_cap WHERE company_id = ? ORDER BY year DESC LIMIT 1", (ticker,))
    m_row = cursor.fetchone()
    if m_row:
        m_cols = [desc[0] for desc in cursor.description]
        comp_info.update(dict(zip(m_cols, m_row)))
        
    conn.close()
    return comp_info

def get_financials_history(ticker: str) -> Dict[str, pd.DataFrame]:
    """Fetch complete historical tables for P&L, BS, and CF for a company."""
    conn = get_connection()
    
    pl = pd.read_sql("SELECT * FROM profitandloss WHERE company_id = ? ORDER BY year ASC", conn, params=(ticker,))
    bs = pd.read_sql("SELECT * FROM balancesheet WHERE company_id = ? ORDER BY year ASC", conn, params=(ticker,))
    cf = pd.read_sql("SELECT * FROM cashflow WHERE company_id = ? ORDER BY year ASC", conn, params=(ticker,))
    ratios = pd.read_sql("SELECT * FROM financial_ratios WHERE company_id = ? ORDER BY year ASC", conn, params=(ticker,))
    
    conn.close()
    return {
        'profitandloss': pl,
        'balancesheet': bs,
        'cashflow': cf,
        'ratios': ratios
    }
