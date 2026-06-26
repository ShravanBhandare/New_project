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

def calculate_cagr(start_val: float | None, end_val: float | None, years: int) -> Tuple[float | None, str]:
    """
    Calculate CAGR percentage.
    CAGR = ((end_val / start_val) ** (1 / years) - 1) * 100
    Turnaround Decision Table:
    - start > 0, end > 0: Normal
    - start <= 0, end > 0: Turnaround (loss to profit)
    - start > 0, end <= 0: Decline to Loss
    - start <= 0, end <= 0: Retained Loss
    """
    if start_val is None or pd_isna(start_val) or end_val is None or pd_isna(end_val):
        return None, 'Missing Data'
        
    s = float(start_val)
    e = float(end_val)
    
    if s > 0 and e > 0:
        val = ((e / s) ** (1 / years) - 1) * 100
        return val, 'Normal'
    elif s <= 0 and e > 0:
        return None, 'Turnaround'
    elif s > 0 and e <= 0:
        return None, 'Decline to Loss'
    else:
        return None, 'Retained Loss'

def pd_isna(val) -> bool:
    """Helper to check if a value is None or NaN."""
    if val is None:
        return True
    try:
        return math.isnan(val)
    except:
        return False

def find_past_value(df_comp: pd.DataFrame, current_year_str: str, years_back: int, column_name: str) -> float | None:
    """Finds target value in history by subtracting years_back from the year string."""
    parts = current_year_str.split('-')
    if len(parts) != 2:
        return None
    try:
        yr = int(parts[0])
        mm = parts[1]
    except ValueError:
        return None
        
    target_yr_str = f"{yr - years_back}-{mm}"
    row = df_comp[df_comp['year'] == target_yr_str]
    if not row.empty:
        val = row.iloc[0][column_name]
        return None if pd_isna(val) else float(val)
    return None

def migrate_cagr_columns(conn: sqlite3.Connection):
    """Ensure all required CAGR columns exist in financial_ratios."""
    cursor = conn.cursor()
    cagr_columns = [
        'sales_cagr_3yr', 'sales_cagr_5yr', 'sales_cagr_10yr',
        'pat_cagr_3yr', 'pat_cagr_5yr', 'pat_cagr_10yr',
        'eps_cagr_3yr', 'eps_cagr_5yr', 'eps_cagr_10yr'
    ]
    for col in cagr_columns:
        try:
            cursor.execute(f"SELECT {col} FROM financial_ratios LIMIT 1")
        except sqlite3.OperationalError:
            logger.info(f"Altering financial_ratios to add {col} column...")
            cursor.execute(f"ALTER TABLE financial_ratios ADD COLUMN {col} NUMERIC")
            conn.commit()

def populate_cagr_ratios(db_path: str = DB_PATH):
    """
    Fetch profitandloss table, calculate 3yr, 5yr, and 10yr CAGR for
    sales, net_profit, and eps, and save to financial_ratios.
    """
    if not os.path.exists(db_path):
        logger.error(f"Database file not found at {db_path}.")
        return

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    migrate_cagr_columns(conn)
    
    # Load all profitandloss statements
    df_pl = pd.read_sql("SELECT company_id, year, sales, net_profit, eps FROM profitandloss", conn)
    
    # Also load all existing financial_ratios keys to ensure rows exist
    df_ratios = pd.read_sql("SELECT id, company_id, year FROM financial_ratios", conn)
    ratios_keys = set(zip(df_ratios['company_id'], df_ratios['year']))
    
    logger.info(f"Loaded {len(df_pl)} profit and loss statements.")
    
    cursor = conn.cursor()
    updates = 0
    inserts = 0

    # Group by company
    companies = df_pl['company_id'].unique()
    for comp in companies:
        df_comp = df_pl[df_pl['company_id'] == comp].copy()
        
        for idx, row in df_comp.iterrows():
            year_str = row['year']
            
            sales_val = None if pd_isna(row['sales']) else float(row['sales'])
            pat_val = None if pd_isna(row['net_profit']) else float(row['net_profit'])
            eps_val = None if pd_isna(row['eps']) else float(row['eps'])
            
            # 3-year values
            sales_3 = find_past_value(df_comp, year_str, 3, 'sales')
            pat_3 = find_past_value(df_comp, year_str, 3, 'net_profit')
            eps_3 = find_past_value(df_comp, year_str, 3, 'eps')
            
            # 5-year values
            sales_5 = find_past_value(df_comp, year_str, 5, 'sales')
            pat_5 = find_past_value(df_comp, year_str, 5, 'net_profit')
            eps_5 = find_past_value(df_comp, year_str, 5, 'eps')
            
            # 10-year values
            sales_10 = find_past_value(df_comp, year_str, 10, 'sales')
            pat_10 = find_past_value(df_comp, year_str, 10, 'net_profit')
            eps_10 = find_past_value(df_comp, year_str, 10, 'eps')
            
            # Calculate CAGRs
            sales_cagr_3, _ = calculate_cagr(sales_3, sales_val, 3)
            sales_cagr_5, _ = calculate_cagr(sales_5, sales_val, 5)
            sales_cagr_10, _ = calculate_cagr(sales_10, sales_val, 10)
            
            pat_cagr_3, pat_flag_3 = calculate_cagr(pat_3, pat_val, 3)
            pat_cagr_5, pat_flag_5 = calculate_cagr(pat_5, pat_val, 5)
            pat_cagr_10, pat_flag_10 = calculate_cagr(pat_10, pat_val, 10)
            
            eps_cagr_3, eps_flag_3 = calculate_cagr(eps_3, eps_val, 3)
            eps_cagr_5, eps_flag_5 = calculate_cagr(eps_5, eps_val, 5)
            eps_cagr_10, eps_flag_10 = calculate_cagr(eps_10, eps_val, 10)
            
            # Log turnarounds for monitoring
            if pat_flag_5 == 'Turnaround':
                logger.info(f"Turnaround detected for {comp} at 5-year PAT: {pat_5} -> {pat_val}")

            # Upsert into financial_ratios
            key = (comp, year_str)
            if key in ratios_keys:
                cursor.execute("""
                    UPDATE financial_ratios
                    SET sales_cagr_3yr = ?, sales_cagr_5yr = ?, sales_cagr_10yr = ?,
                        pat_cagr_3yr = ?, pat_cagr_5yr = ?, pat_cagr_10yr = ?,
                        eps_cagr_3yr = ?, eps_cagr_5yr = ?, eps_cagr_10yr = ?
                    WHERE company_id = ? AND year = ?
                """, (
                    sales_cagr_3, sales_cagr_5, sales_cagr_10,
                    pat_cagr_3, pat_cagr_5, pat_cagr_10,
                    eps_cagr_3, eps_cagr_5, eps_cagr_10,
                    comp, year_str
                ))
                updates += 1
            else:
                cursor.execute("""
                    INSERT INTO financial_ratios (
                        company_id, year, 
                        sales_cagr_3yr, sales_cagr_5yr, sales_cagr_10yr,
                        pat_cagr_3yr, pat_cagr_5yr, pat_cagr_10yr,
                        eps_cagr_3yr, eps_cagr_5yr, eps_cagr_10yr
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    comp, year_str,
                    sales_cagr_3, sales_cagr_5, sales_cagr_10,
                    pat_cagr_3, pat_cagr_5, pat_cagr_10,
                    eps_cagr_3, eps_cagr_5, eps_cagr_10
                ))
                inserts += 1

    conn.commit()
    conn.close()
    logger.info(f"CAGR computation complete. Updated: {updates} records. Inserted: {inserts} records.")

if __name__ == "__main__":
    populate_cagr_ratios()
