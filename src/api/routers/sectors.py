import sqlite3
import pandas as pd
import numpy as np
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any

router = APIRouter(prefix="/sectors", tags=["Sectors"])
DB_PATH = "data/nifty100.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@router.get("", response_model=List[Dict[str, Any]])
def list_sectors():
    """Retrieve unique broad sectors and aggregate statistics."""
    conn = get_db_connection()
    
    # Query companies with sector and latest financial ratios
    query = """
    SELECT 
        s.broad_sector,
        r.return_on_equity_pct, r.debt_to_equity, r.net_profit_margin_pct, r.operating_profit_margin_pct,
        mc.market_cap_crore, mc.pe_ratio, mc.dividend_yield_pct
    FROM sectors s
    LEFT JOIN financial_ratios r ON s.company_id = r.company_id AND r.year = (
        SELECT MAX(year) FROM financial_ratios WHERE company_id = s.company_id
    )
    LEFT JOIN market_cap mc ON s.company_id = mc.company_id AND mc.year = 2024
    """
    df = pd.read_sql(query, conn)
    conn.close()
    
    if df.empty:
        raise HTTPException(status_code=404, detail="No sector/company data found")
        
    # Group by broad_sector and calculate medians and sums
    grouped = df.groupby('broad_sector').agg(
        constituents_count=('broad_sector', 'count'),
        total_market_cap=('market_cap_crore', 'sum'),
        median_roe=('return_on_equity_pct', 'median'),
        median_de=('debt_to_equity', 'median'),
        median_npm=('net_profit_margin_pct', 'median'),
        median_opm=('operating_profit_margin_pct', 'median'),
        median_pe=('pe_ratio', 'median'),
        median_div_yield=('dividend_yield_pct', 'median')
    ).reset_index()
    
    # Round numerical fields for clean JSON
    for col in grouped.columns:
        if col != 'broad_sector':
            grouped[col] = grouped[col].round(2).replace([np.nan, None, float('inf'), float('-inf')], None)
            
    return grouped.to_dict(orient="records")

@router.get("/{sector_name}/constituents", response_model=List[Dict[str, Any]])
def get_sector_constituents(sector_name: str):
    """Retrieve list of companies in a specific sector with their key metrics."""
    conn = get_db_connection()
    query = """
    SELECT s.company_id, c.company_name, s.sub_sector, s.index_weight_pct,
           r.return_on_equity_pct, r.debt_to_equity, r.net_profit_margin_pct,
           mc.market_cap_crore, mc.pe_ratio
    FROM sectors s
    JOIN companies c ON s.company_id = c.id
    LEFT JOIN financial_ratios r ON s.company_id = r.company_id AND r.year = (
        SELECT MAX(year) FROM financial_ratios WHERE company_id = s.company_id
    )
    LEFT JOIN market_cap mc ON s.company_id = mc.company_id AND mc.year = 2024
    WHERE s.broad_sector = ?
    """
    df = pd.read_sql(query, conn, params=(sector_name,))
    conn.close()
    
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No constituents found for sector '{sector_name}'")
        
    df = df.round(2).replace([np.nan, None], None)
    return df.to_dict(orient="records")
