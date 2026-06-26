import sqlite3
import logging
import os
import math
from typing import Dict, Any, List, Set

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = "data/nifty100.db"

def calculate_npm(net_profit: float, sales: float) -> float | None:
    """
    Calculate Net Profit Margin (NPM) percentage.
    NPM = (Net Profit / Sales) * 100
    Edge case: Return None if sales is zero or negative.
    """
    if sales is None or pd_isna(sales) or sales <= 0:
        return None
    if net_profit is None or pd_isna(net_profit):
        return None
    return (net_profit / sales) * 100

def calculate_opm(operating_profit: float, sales: float) -> float | None:
    """
    Calculate Operating Profit Margin (OPM) percentage.
    OPM = (Operating Profit / Sales) * 100
    Edge case: Return None if sales is zero or negative.
    """
    if sales is None or pd_isna(sales) or sales <= 0:
        return None
    if operating_profit is None or pd_isna(operating_profit):
        return None
    return (operating_profit / sales) * 100

def calculate_roe(net_profit: float, equity_capital: float, reserves: float) -> float | None:
    """
    Calculate Return on Equity (ROE) percentage.
    ROE = (Net Profit / (Equity Capital + Reserves)) * 100
    Edge case: If equity + reserves <= 0 (negative equity), log as anomaly and return None.
    """
    if net_profit is None or pd_isna(net_profit):
        return None
    eq = 0.0 if (equity_capital is None or pd_isna(equity_capital)) else equity_capital
    res = 0.0 if (reserves is None or pd_isna(reserves)) else reserves
    tot_equity = eq + res
    if tot_equity <= 0:
        logger.warning(f"Anomaly: Non-positive equity capital + reserves ({tot_equity}) for ROE calculation.")
        return None
    return (net_profit / tot_equity) * 100

def calculate_roce(profit_before_tax: float, interest: float, equity_capital: float, reserves: float, borrowings: float) -> float | None:
    """
    Calculate Return on Capital Employed (ROCE) percentage.
    ROCE = (EBIT / Capital Employed) * 100
    EBIT = Profit Before Tax + Interest
    Capital Employed = Equity Capital + Reserves + Borrowings
    Edge case: Return None if Capital Employed <= 0.
    """
    pbt = 0.0 if (profit_before_tax is None or pd_isna(profit_before_tax)) else profit_before_tax
    intr = 0.0 if (interest is None or pd_isna(interest)) else interest
    ebit = pbt + intr
    
    eq = 0.0 if (equity_capital is None or pd_isna(equity_capital)) else equity_capital
    res = 0.0 if (reserves is None or pd_isna(reserves)) else reserves
    br = 0.0 if (borrowings is None or pd_isna(borrowings)) else borrowings
    
    cap_employed = eq + res + br
    if cap_employed <= 0:
        logger.warning(f"Anomaly: Non-positive capital employed ({cap_employed}) for ROCE calculation.")
        return None
        
    return (ebit / cap_employed) * 100

def calculate_de(borrowings: float, equity_capital: float, reserves: float, company_id: str, financial_companies: Set[str]) -> float | None:
    """
    Calculate Debt-to-Equity (D/E) ratio.
    D/E = Borrowings / (Equity Capital + Reserves)
    Bank carve-out: Return None if company is a financial company.
    Edge case: Return None if total equity is <= 0.
    """
    if company_id in financial_companies:
        return None
        
    br = 0.0 if (borrowings is None or pd_isna(borrowings)) else borrowings
    eq = 0.0 if (equity_capital is None or pd_isna(equity_capital)) else equity_capital
    res = 0.0 if (reserves is None or pd_isna(reserves)) else reserves
    tot_equity = eq + res
    if tot_equity <= 0:
        return None
        
    return br / tot_equity

def calculate_icr(profit_before_tax: float, interest: float) -> float | None:
    """
    Calculate Interest Coverage Ratio (ICR).
    ICR = EBIT / Interest = (Profit Before Tax + Interest) / Interest
    Edge case: Debt-free substitution. If interest is None or <= 0, return 999.0.
    """
    pbt = 0.0 if (profit_before_tax is None or pd_isna(profit_before_tax)) else profit_before_tax
    intr = 0.0 if (interest is None or pd_isna(interest)) else interest
    
    if intr <= 0:
        return 999.0
        
    ebit = pbt + intr
    return ebit / intr

def calculate_asset_turnover(sales: float, total_assets: float) -> float | None:
    """
    Calculate Asset Turnover ratio.
    Asset Turnover = Sales / Total Assets
    Edge case: Return None if Total Assets is <= 0 or missing.
    """
    if total_assets is None or pd_isna(total_assets) or total_assets <= 0:
        return None
    s = 0.0 if (sales is None or pd_isna(sales)) else sales
    return s / total_assets

def pd_isna(val) -> bool:
    """Helper to check if a value is None or NaN."""
    if val is None:
        return True
    try:
        return math.isnan(val)
    except:
        return False

def populate_profitability_ratios(db_path: str = DB_PATH):
    """
    Loads P&L and Balance Sheet tables from SQLite, calculates profitability,
    leverage, and efficiency ratios, and writes to financial_ratios table.
    """
    if not os.path.exists(db_path):
        logger.error(f"Database file not found at {db_path}.")
        return

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()

    # Ensure financial_ratios table has return_on_capital_employed_pct column
    try:
        cursor.execute("SELECT return_on_capital_employed_pct FROM financial_ratios LIMIT 1")
    except sqlite3.OperationalError:
        logger.info("Altering financial_ratios to add return_on_capital_employed_pct column...")
        cursor.execute("ALTER TABLE financial_ratios ADD COLUMN return_on_capital_employed_pct NUMERIC")
        conn.commit()

    # Fetch sector mapping to identify financial companies (bank carve-out)
    cursor.execute("SELECT company_id, broad_sector, sub_sector FROM sectors")
    sec_rows = cursor.fetchall()
    financial_sectors = {'Financials', 'Private Banks', 'Public Sector Banks', 'Life Insurance', 'Consumer Finance'}
    financial_companies = set()
    for s_row in sec_rows:
        c_id, broad, sub = s_row
        if broad in financial_sectors or sub in financial_sectors:
            financial_companies.add(c_id)

    # Query all years and companies that have profitandloss records
    query = """
        SELECT 
            pl.company_id, pl.year, pl.sales, pl.operating_profit, pl.opm_percentage, 
            pl.profit_before_tax, pl.interest, pl.net_profit,
            bs.equity_capital, bs.reserves, bs.borrowings, bs.total_assets
        FROM profitandloss pl
        LEFT JOIN balancesheet bs ON pl.company_id = bs.company_id AND pl.year = bs.year
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    
    logger.info(f"Retrieved {len(rows)} matching statements to calculate ratios.")
    
    mismatches = 0
    updates_count = 0

    for row in rows:
        comp_id, year, sales, op, source_opm, pbt, interest, np, eq, res, br, assets = row
        
        npm = calculate_npm(np, sales)
        opm = calculate_opm(op, sales)
        roe = calculate_roe(np, eq, res)
        roce = calculate_roce(pbt, interest, eq, res, br)
        
        de = calculate_de(br, eq, res, comp_id, financial_companies)
        icr = calculate_icr(pbt, interest)
        asset_turnover = calculate_asset_turnover(sales, assets)
        
        # Cross-validate OPM vs source sheet
        if opm is not None and source_opm is not None:
            if abs(opm - source_opm) >= 1.0:
                mismatches += 1

        # Upsert into financial_ratios table
        cursor.execute("SELECT id FROM financial_ratios WHERE company_id = ? AND year = ?", (comp_id, year))
        ratio_row = cursor.fetchone()
        
        if ratio_row:
            cursor.execute("""
                UPDATE financial_ratios
                SET net_profit_margin_pct = ?,
                    operating_profit_margin_pct = ?,
                    return_on_equity_pct = ?,
                    return_on_capital_employed_pct = ?,
                    debt_to_equity = ?,
                    interest_coverage = ?,
                    asset_turnover = ?
                WHERE company_id = ? AND year = ?
            """, (npm, opm, roe, roce, de, icr, asset_turnover, comp_id, year))
        else:
            cursor.execute("""
                INSERT INTO financial_ratios (
                    company_id, year, net_profit_margin_pct, operating_profit_margin_pct, 
                    return_on_equity_pct, return_on_capital_employed_pct, 
                    debt_to_equity, interest_coverage, asset_turnover
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (comp_id, year, npm, opm, roe, roce, de, icr, asset_turnover))

        updates_count += 1
        
    conn.commit()
    conn.close()
    
    logger.info(f"Populated ratios for {updates_count} records. Total OPM mismatches: {mismatches}")

if __name__ == "__main__":
    populate_profitability_ratios()
