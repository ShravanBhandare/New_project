import sqlite3
import logging
import os
import math
import pandas as pd
from typing import Dict, Any, List, Tuple

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = "data/nifty100.db"

def calculate_fcf(cfo: float | None, capex: float | None) -> float | None:
    """
    Calculate Free Cash Flow (FCF).
    FCF = CFO - CapEx
    """
    if cfo is None or pd_isna(cfo) or capex is None or pd_isna(capex):
        return None
    return float(cfo) - float(capex)

def calculate_cfo_quality(cfo: float | None, net_profit: float | None) -> float | None:
    """
    Calculate CFO Quality Score.
    Quality Score = CFO / Net Profit
    Edge Case: Return None if Net Profit is <= 0.
    """
    if cfo is None or pd_isna(cfo) or net_profit is None or pd_isna(net_profit):
        return None
    np = float(net_profit)
    if np <= 0:
        return None
    return float(cfo) / np

def calculate_capex_intensity(capex: float | None, sales: float | None) -> float | None:
    """
    Calculate CapEx Intensity percentage.
    Intensity = (CapEx / Sales) * 100
    Edge Case: Return None if Sales is <= 0.
    """
    if capex is None or pd_isna(capex) or sales is None or pd_isna(sales):
        return None
    s = float(sales)
    if s <= 0:
        return None
    return (float(capex) / s) * 100

def calculate_fcf_conversion(fcf: float | None, net_profit: float | None) -> float | None:
    """
    Calculate FCF Conversion percentage.
    Conversion = (FCF / Net Profit) * 100
    Edge Case: Return None if Net Profit is <= 0.
    """
    if fcf is None or pd_isna(fcf) or net_profit is None or pd_isna(net_profit):
        return None
    np = float(net_profit)
    if np <= 0:
        return None
    return (float(fcf) / np) * 100

def classify_capital_allocation(cfo: float | None, cfi: float | None, cff: float | None) -> str:
    """
    Classify sign combination of CFO, CFI, CFF into one of 8 capital allocation classes.
    1. (+, -, -) -> Healthy/Mature
    2. (+, -, +) -> Growth/Expansion
    3. (+, +, -) -> Asset Seller/Deleveraging
    4. (+, +, +) -> Cash Accumulator
    5. (-, -, +) -> Startup/Early Stage
    6. (-, -, -) -> Severe Cash Burn
    7. (-, +, +) -> Restructuring/Survival
    8. (-, +, -) -> Asset Liquidation
    """
    o = 0.0 if (cfo is None or pd_isna(cfo)) else float(cfo)
    i = 0.0 if (cfi is None or pd_isna(cfi)) else float(cfi)
    f = 0.0 if (cff is None or pd_isna(cff)) else float(cff)
    
    if o > 0:
        if i < 0:
            return 'Healthy/Mature' if f < 0 else 'Growth/Expansion'
        else:
            return 'Asset Seller/Deleveraging' if f < 0 else 'Cash Accumulator'
    else:
        if i < 0:
            return 'Severe Cash Burn' if f < 0 else 'Startup/Early Stage'
        else:
            return 'Asset Liquidation' if f < 0 else 'Restructuring/Survival'

def pd_isna(val) -> bool:
    """Helper to check if a value is None or NaN."""
    if val is None:
        return True
    try:
        return math.isnan(val)
    except:
        return False

def migrate_cashflow_columns(conn: sqlite3.Connection):
    """Ensure cash flow KPI columns exist in financial_ratios."""
    cursor = conn.cursor()
    columns = [
        'cfo_quality_score',
        'capex_intensity_pct',
        'fcf_conversion_pct',
        'capital_allocation_pattern'
    ]
    for col in columns:
        try:
            cursor.execute(f"SELECT {col} FROM financial_ratios LIMIT 1")
        except sqlite3.OperationalError:
            # Determine type
            col_type = "TEXT" if col == 'capital_allocation_pattern' else "NUMERIC"
            logger.info(f"Altering financial_ratios to add {col} ({col_type}) column...")
            cursor.execute(f"ALTER TABLE financial_ratios ADD COLUMN {col} {col_type}")
            conn.commit()

def populate_cashflow_kpis(db_path: str = DB_PATH):
    """
    Fetch profitandloss, cashflow, and financial_ratios.
    Compute cash flow KPIs and update financial_ratios table.
    """
    if not os.path.exists(db_path):
        logger.error(f"Database file not found at {db_path}.")
        return

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    migrate_cashflow_columns(conn)
    
    # Query P&L (sales, net_profit), Cashflow (operating, investing, financing), 
    # and financial_ratios (capex_cr)
    query = """
        SELECT 
            fr.company_id, fr.year, fr.capex_cr,
            pl.sales, pl.net_profit,
            cf.operating_activity, cf.investing_activity, cf.financing_activity
        FROM financial_ratios fr
        LEFT JOIN profitandloss pl ON fr.company_id = pl.company_id AND fr.year = pl.year
        LEFT JOIN cashflow cf ON fr.company_id = cf.company_id AND fr.year = cf.year
    """
    cursor = conn.cursor()
    cursor.execute(query)
    rows = cursor.fetchall()
    
    logger.info(f"Retrieved {len(rows)} statements to process cash flow KPIs.")
    
    updates = 0
    for row in rows:
        comp_id, year, capex, sales, net_profit, cfo, cfi, cff = row
        
        # Free Cash Flow (FCF)
        # Use capex_cr from financial_ratios and operating_activity from cashflow
        fcf = calculate_fcf(cfo, capex)
        
        # CFO Quality Score
        cfo_quality = calculate_cfo_quality(cfo, net_profit)
        
        # CapEx Intensity
        capex_intensity = calculate_capex_intensity(capex, sales)
        
        # FCF Conversion
        fcf_conversion = calculate_fcf_conversion(fcf, net_profit)
        
        # Capital Allocation Pattern
        pattern = classify_capital_allocation(cfo, cfi, cff)
        
        # Update financial_ratios
        cursor.execute("""
            UPDATE financial_ratios
            SET free_cash_flow_cr = ?,
                cfo_quality_score = ?,
                capex_intensity_pct = ?,
                fcf_conversion_pct = ?,
                capital_allocation_pattern = ?
            WHERE company_id = ? AND year = ?
        """, (fcf, cfo_quality, capex_intensity, fcf_conversion, pattern, comp_id, year))
        updates += 1
        
    conn.commit()
    conn.close()
    logger.info(f"Cash flow KPI population complete. Updated {updates} records.")

if __name__ == "__main__":
    populate_cashflow_kpis()
