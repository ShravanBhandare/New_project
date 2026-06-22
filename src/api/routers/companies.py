import sqlite3
import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any

router = APIRouter(prefix="/companies", tags=["Companies"])
DB_PATH = "data/nifty100.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@router.get("", response_model=List[Dict[str, Any]])
def list_companies(
    q: Optional[str] = Query(None, description="Search by ticker or name"),
    sector: Optional[str] = Query(None, description="Filter by broad sector")
):
    """Retrieve all constituent companies with optional search and sector filters."""
    conn = get_db_connection()
    query = """
    SELECT c.id, c.company_name, s.broad_sector, s.sub_sector, s.index_weight_pct
    FROM companies c
    LEFT JOIN sectors s ON c.id = s.company_id
    WHERE 1=1
    """
    params = []
    
    if q:
        query += " AND (c.id LIKE ? OR c.company_name LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])
        
    if sector:
        query += " AND s.broad_sector = ?"
        params.append(sector)
        
    df = pd.read_sql(query, conn, params=params)
    conn.close()
    return df.to_dict(orient="records")

@router.get("/{ticker}", response_model=Dict[str, Any])
def get_company_profile(ticker: str):
    """Get full profile details for a given company ticker."""
    conn = get_db_connection()
    ticker_upper = ticker.upper()
    
    query = """
    SELECT c.*, s.broad_sector, s.sub_sector, s.index_weight_pct,
           cc.cluster_name, cc.cluster_description
    FROM companies c
    LEFT JOIN sectors s ON c.id = s.company_id
    LEFT JOIN company_clusters cc ON c.id = cc.company_id
    WHERE c.id = ?
    """
    df = pd.read_sql(query, conn, params=(ticker_upper,))
    
    # Get pros and cons
    pc_df = pd.read_sql("SELECT pros, cons FROM prosandcons WHERE company_id = ?", conn, params=(ticker_upper,))
    
    conn.close()
    
    if df.empty:
        raise HTTPException(status_code=404, detail="Company not found")
        
    profile = df.iloc[0].to_dict()
    profile['pros'] = list(set([row['pros'] for _, row in pc_df.iterrows() if row['pros']]))
    profile['cons'] = list(set([row['cons'] for _, row in pc_df.iterrows() if row['cons']]))
    
    return profile

@router.get("/{ticker}/pl", response_model=List[Dict[str, Any]])
def get_company_pl(ticker: str):
    """Retrieve historical Profit & Loss statements for a given ticker."""
    conn = get_db_connection()
    ticker_upper = ticker.upper()
    
    df = pd.read_sql("SELECT * FROM profitandloss WHERE company_id = ? ORDER BY year", conn, params=(ticker_upper,))
    conn.close()
    
    if df.empty:
        raise HTTPException(status_code=404, detail="Company P&L data not found")
        
    return df.to_dict(orient="records")

@router.get("/{ticker}/bs", response_model=List[Dict[str, Any]])
def get_company_bs(ticker: str):
    """Retrieve historical Balance Sheet statements for a given ticker."""
    conn = get_db_connection()
    ticker_upper = ticker.upper()
    
    df = pd.read_sql("SELECT * FROM balancesheet WHERE company_id = ? ORDER BY year", conn, params=(ticker_upper,))
    conn.close()
    
    if df.empty:
        raise HTTPException(status_code=404, detail="Company Balance Sheet data not found")
        
    return df.to_dict(orient="records")

@router.get("/{ticker}/cashflow", response_model=List[Dict[str, Any]])
def get_company_cashflow(ticker: str):
    """Retrieve historical Cash Flow statements for a given ticker."""
    conn = get_db_connection()
    ticker_upper = ticker.upper()
    
    df = pd.read_sql("SELECT * FROM cashflow WHERE company_id = ? ORDER BY year", conn, params=(ticker_upper,))
    conn.close()
    
    if df.empty:
        raise HTTPException(status_code=404, detail="Company Cash Flow data not found")
        
    return df.to_dict(orient="records")

@router.get("/{ticker}/ratios", response_model=List[Dict[str, Any]])
def get_company_ratios(ticker: str):
    """Retrieve historical computed financial ratios for a given ticker."""
    conn = get_db_connection()
    ticker_upper = ticker.upper()
    
    df = pd.read_sql("SELECT * FROM financial_ratios WHERE company_id = ? ORDER BY year", conn, params=(ticker_upper,))
    conn.close()
    
    if df.empty:
        raise HTTPException(status_code=404, detail="Company ratio data not found")
        
    return df.to_dict(orient="records")
