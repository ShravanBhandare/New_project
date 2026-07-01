import sqlite3
import logging
import os
import math
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Set, Tuple

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = "data/nifty100.db"

def pd_isna(val) -> bool:
    """Helper to check if a value is None or NaN."""
    if val is None:
        return True
    try:
        if isinstance(val, (int, float)):
            return math.isnan(val)
        return False
    except:
        return False

def calculate_cagr(start_val: float | None, end_val: float | None, years: int) -> float | None:
    """Calculate CAGR percentage. Returns None if start or end is non-positive."""
    if start_val is None or pd_isna(start_val) or end_val is None or pd_isna(end_val):
        return None
    s = float(start_val)
    e = float(end_val)
    if s > 0 and e > 0:
        try:
            return ((e / s) ** (1 / years) - 1) * 100
        except:
            return None
    return None

def score_de(de_val: float) -> float:
    """Calculate D/E score based on spec mapping: 0=100, 0.5=85, 1=70, 2=50, >5=0."""
    if pd_isna(de_val) or de_val < 0:
        return 0.0
    if de_val == 0:
        return 100.0
    elif de_val <= 0.5:
        return 100.0 - (de_val / 0.5) * 15.0
    elif de_val <= 1.0:
        return 85.0 - ((de_val - 0.5) / 0.5) * 15.0
    elif de_val <= 2.0:
        return 70.0 - ((de_val - 1.0) / 1.0) * 20.0
    elif de_val <= 5.0:
        return 50.0 - ((de_val - 2.0) / 3.0) * 50.0
    else:
        return 0.0

def score_icr(icr_val: float) -> float:
    """Calculate ICR score based on spec mapping: >10=100, 5=75, 3=50, <1.5=0."""
    if pd_isna(icr_val):
        return 0.0
    if icr_val >= 10.0:
        return 100.0
    elif icr_val >= 5.0:
        return 75.0 + ((icr_val - 5.0) / 5.0) * 25.0
    elif icr_val >= 3.0:
        return 50.0 + ((icr_val - 3.0) / 2.0) * 25.0
    elif icr_val >= 1.5:
        return 0.0 + ((icr_val - 1.5) / 1.5) * 50.0
    else:
        return 0.0

def winsorise_and_scale(series: pd.Series) -> pd.Series:
    """Cap series values at P10 and P90, then scale linearly to [0, 100]."""
    if series.empty:
        return series
    
    filled = series.fillna(0.0)
    p10 = filled.quantile(0.10)
    p90 = filled.quantile(0.90)
    
    capped = filled.clip(lower=p10, upper=p90)
    
    if p90 == p10:
        return pd.Series(100.0, index=series.index)
        
    scaled = ((capped - p10) / (p90 - p10)) * 100.0
    return scaled

def migrate_master_columns(conn: sqlite3.Connection):
    """Ensure required KPI columns exist in financial_ratios."""
    cursor = conn.cursor()
    columns_with_types = {
        'revenue_cagr_5yr': 'NUMERIC',
        'composite_quality_score': 'NUMERIC',
        'return_on_capital_employed_pct': 'NUMERIC',
        'sales_cagr_3yr': 'NUMERIC',
        'sales_cagr_5yr': 'NUMERIC',
        'sales_cagr_10yr': 'NUMERIC',
        'pat_cagr_3yr': 'NUMERIC',
        'pat_cagr_5yr': 'NUMERIC',
        'pat_cagr_10yr': 'NUMERIC',
        'eps_cagr_3yr': 'NUMERIC',
        'eps_cagr_5yr': 'NUMERIC',
        'eps_cagr_10yr': 'NUMERIC'
    }
    for col, col_type in columns_with_types.items():
        try:
            cursor.execute(f"SELECT {col} FROM financial_ratios LIMIT 1")
        except sqlite3.OperationalError:
            logger.info(f"Altering financial_ratios to add {col} ({col_type}) column...")
            cursor.execute(f"ALTER TABLE financial_ratios ADD COLUMN {col} {col_type}")
            conn.commit()

def run_master_engine(db_path: str = DB_PATH):
    """Run full ratio engine calculations and populate the database."""
    if not os.path.exists(db_path):
        logger.error(f"Database file not found at {db_path}.")
        return

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    
    # 1. Migrate columns
    migrate_master_columns(conn)
    
    # 2. Insert missing keys from the union of PL and BS statements
    cursor = conn.cursor()
    logger.info("Inserting missing keys into financial_ratios...")
    cursor.execute("""
        INSERT OR IGNORE INTO financial_ratios (company_id, year)
        SELECT company_id, year FROM profitandloss
        UNION
        SELECT company_id, year FROM balancesheet
    """)
    conn.commit()
    
    # 3. Load all statements from tables into memory
    df_pl = pd.read_sql("SELECT * FROM profitandloss", conn)
    df_bs = pd.read_sql("SELECT * FROM balancesheet", conn)
    df_cf = pd.read_sql("SELECT * FROM cashflow", conn)
    df_fr_existing = pd.read_sql("SELECT * FROM financial_ratios", conn)
    
    # Sector mapping for D/E bank carve-out
    df_sec = pd.read_sql("SELECT company_id, broad_sector, sub_sector FROM sectors", conn)
    financial_sectors = {'Financials', 'Private Banks', 'Public Sector Banks', 'Life Insurance', 'Consumer Finance'}
    financial_companies = set(
        df_sec[df_sec['broad_sector'].isin(financial_sectors) | df_sec['sub_sector'].isin(financial_sectors)]['company_id']
    )
    
    logger.info(f"Loaded records: PL={len(df_pl)}, BS={len(df_bs)}, CF={len(df_cf)}, FR={len(df_fr_existing)}")
    
    # Use indexes for fast historical lookups
    df_pl.set_index(['company_id', 'year'], inplace=True)
    df_bs.set_index(['company_id', 'year'], inplace=True)
    df_cf.set_index(['company_id', 'year'], inplace=True)
    df_fr_existing.set_index(['company_id', 'year'], inplace=True)
    
    all_keys = df_fr_existing.index.tolist()
    calculated_rows = []
    
    # For CAGR lookups
    def find_past_val(comp: str, year_str: str, years_back: int, df_source, col_name: str) -> float | None:
        parts = year_str.split('-')
        if len(parts) != 2:
            return None
        try:
            yr = int(parts[0])
            mm = parts[1]
        except ValueError:
            return None
        past_yr_str = f"{yr - years_back}-{mm}"
        if (comp, past_yr_str) in df_source.index:
            val = df_source.loc[(comp, past_yr_str), col_name]
            if isinstance(val, pd.Series):
                val = val.iloc[0]
            return None if pd_isna(val) else float(val)
        return None

    logger.info("Computing metrics for all keys...")
    
    for comp_id, year in all_keys:
        # Load statement metrics
        # 1. P&L
        sales = None
        op = None
        pbt = None
        interest = None
        np_val = None
        eps = None
        if (comp_id, year) in df_pl.index:
            pl_row = df_pl.loc[(comp_id, year)]
            sales = float(pl_row['sales']) if not pd_isna(pl_row['sales']) else None
            op = float(pl_row['operating_profit']) if not pd_isna(pl_row['operating_profit']) else None
            pbt = float(pl_row['profit_before_tax']) if not pd_isna(pl_row['profit_before_tax']) else None
            interest = float(pl_row['interest']) if not pd_isna(pl_row['interest']) else None
            np_val = float(pl_row['net_profit']) if not pd_isna(pl_row['net_profit']) else None
            eps = float(pl_row['eps']) if not pd_isna(pl_row['eps']) else None
            
        # 2. Balance Sheet
        eq_cap = None
        reserves = None
        borrowings = None
        assets = None
        if (comp_id, year) in df_bs.index:
            bs_row = df_bs.loc[(comp_id, year)]
            eq_cap = float(bs_row['equity_capital']) if not pd_isna(bs_row['equity_capital']) else None
            reserves = float(bs_row['reserves']) if not pd_isna(bs_row['reserves']) else None
            borrowings = float(bs_row['borrowings']) if not pd_isna(bs_row['borrowings']) else None
            assets = float(bs_row['total_assets']) if not pd_isna(bs_row['total_assets']) else None
            
        # 3. Cash Flow
        cfo_activity = None
        cfi_activity = None
        cff_activity = None
        if (comp_id, year) in df_cf.index:
            cf_row = df_cf.loc[(comp_id, year)]
            cfo_activity = float(cf_row['operating_activity']) if not pd_isna(cf_row['operating_activity']) else None
            cfi_activity = float(cf_row['investing_activity']) if not pd_isna(cf_row['investing_activity']) else None
            cff_activity = float(cf_row['financing_activity']) if not pd_isna(cf_row['financing_activity']) else None

        # 4. Existing FR row
        fr_row = df_fr_existing.loc[(comp_id, year)]
        capex_val = float(fr_row['capex_cr']) if not pd_isna(fr_row['capex_cr']) else 0.0
        bvps = float(fr_row['book_value_per_share']) if not pd_isna(fr_row['book_value_per_share']) else None
        div_payout = float(fr_row['dividend_payout_ratio_pct']) if not pd_isna(fr_row['dividend_payout_ratio_pct']) else None
        
        # Calculate calculated ratios
        # NPM
        npm = (np_val / sales * 100.0) if (np_val is not None and sales is not None and sales > 0) else None
        # OPM
        opm = (op / sales * 100.0) if (op is not None and sales is not None and sales > 0) else None
        # ROE
        tot_eq = (eq_cap or 0.0) + (reserves or 0.0)
        roe = (np_val / tot_eq * 100.0) if (np_val is not None and tot_eq > 0) else None
        # ROCE
        ebit = (pbt or 0.0) + (interest or 0.0)
        cap_employed = tot_eq + (borrowings or 0.0)
        roce = (ebit / cap_employed * 100.0) if (cap_employed > 0) else None
        
        # D/E
        de = None
        if comp_id not in financial_companies:
            de = (borrowings / tot_eq) if (borrowings is not None and tot_eq > 0) else None
            
        # ICR
        icr = 999.0
        if interest is not None and interest > 0:
            icr = ebit / interest
            
        # Asset Turnover
        asset_turnover = (sales / assets) if (sales is not None and assets is not None and assets > 0) else None
        
        # FCF, CapEx, CFO
        cfo = cfo_activity if (cfo_activity is not None) else 0.0
        capex = capex_val
        fcf = cfo - capex
        
        # CAGRs (5-year)
        sales_5 = find_past_val(comp_id, year, 5, df_pl, 'sales')
        pat_5 = find_past_val(comp_id, year, 5, df_pl, 'net_profit')
        eps_5 = find_past_val(comp_id, year, 5, df_pl, 'eps')
        
        sales_cagr_5 = calculate_cagr(sales_5, sales, 5)
        pat_cagr_5 = calculate_cagr(pat_5, np_val, 5)
        eps_cagr_5 = calculate_cagr(eps_5, eps, 5)
        
        # 3yr & 10yr CAGRs for other columns
        sales_3 = find_past_val(comp_id, year, 3, df_pl, 'sales')
        sales_10 = find_past_val(comp_id, year, 10, df_pl, 'sales')
        sales_cagr_3 = calculate_cagr(sales_3, sales, 3)
        sales_cagr_10 = calculate_cagr(sales_10, sales, 10)
        
        pat_3 = find_past_val(comp_id, year, 3, df_pl, 'net_profit')
        pat_10 = find_past_val(comp_id, year, 10, df_pl, 'net_profit')
        pat_cagr_3 = calculate_cagr(pat_3, np_val, 3)
        pat_cagr_10 = calculate_cagr(pat_10, np_val, 10)
        
        eps_3 = find_past_val(comp_id, year, 3, df_pl, 'eps')
        eps_10 = find_past_val(comp_id, year, 10, df_pl, 'eps')
        eps_cagr_3 = calculate_cagr(eps_3, eps, 3)
        eps_cagr_10 = calculate_cagr(eps_10, eps, 10)

        # FCF 5-year CAGR (for composite score)
        fcf_5 = None
        cfo_5 = find_past_val(comp_id, year, 5, df_cf, 'operating_activity')
        capex_5 = find_past_val(comp_id, year, 5, df_fr_existing, 'capex_cr') or 0.0
        if cfo_5 is not None:
            fcf_5 = cfo_5 - capex_5
        fcf_cagr_5 = calculate_cagr(fcf_5, fcf, 5)

        calculated_rows.append({
            'company_id': comp_id,
            'year': year,
            'net_profit_margin_pct': npm,
            'operating_profit_margin_pct': opm,
            'return_on_equity_pct': roe,
            'return_on_capital_employed_pct': roce,
            'debt_to_equity': de,
            'interest_coverage': icr,
            'asset_turnover': asset_turnover,
            'free_cash_flow_cr': fcf,
            'capex_cr': capex,
            'earnings_per_share': eps,
            'book_value_per_share': bvps,
            'dividend_payout_ratio_pct': div_payout,
            'total_debt_cr': borrowings if borrowings is not None else 0.0,
            'cash_from_operations_cr': cfo,
            'revenue_cagr_5yr': sales_cagr_5,
            'pat_cagr_5yr': pat_cagr_5,
            'eps_cagr_5yr': eps_cagr_5,
            'sales_cagr_3yr': sales_cagr_3,
            'sales_cagr_5yr': sales_cagr_5,
            'sales_cagr_10yr': sales_cagr_10,
            'pat_cagr_3yr': pat_cagr_3,
            'pat_cagr_10yr': pat_cagr_10,
            'eps_cagr_3yr': eps_cagr_3,
            'eps_cagr_10yr': eps_cagr_10,
            'fcf_cagr_5yr': fcf_cagr_5 if fcf_cagr_5 is not None else 0.0,
            'net_profit': np_val or 0.0
        })
        
    df_calc = pd.DataFrame(calculated_rows)
    
    # 4. Compute composite quality score cross-sectionally by year
    df_calc['composite_quality_score'] = 0.0
    
    years_present = df_calc['year'].unique()
    for yr in years_present:
        idx_yr = df_calc['year'] == yr
        df_yr = df_calc[idx_yr].copy()
        
        roe_s = winsorise_and_scale(df_yr['return_on_equity_pct'])
        roce_s = winsorise_and_scale(df_yr['return_on_capital_employed_pct'])
        npm_s = winsorise_and_scale(df_yr['net_profit_margin_pct'])
        
        fcf_cagr_s = winsorise_and_scale(df_yr['fcf_cagr_5yr'])
        
        cfo_pat_ratio = df_yr.apply(
            lambda r: (r['cash_from_operations_cr'] / r['net_profit']) if (r['net_profit'] != 0) else 0.0, axis=1
        )
        cfo_pat_s = winsorise_and_scale(cfo_pat_ratio)
        fcf_flag_s = df_yr['free_cash_flow_cr'].apply(lambda x: 100.0 if (x is not None and x > 0) else 0.0)
        
        rev_cagr_s = winsorise_and_scale(df_yr['revenue_cagr_5yr'])
        pat_cagr_s = winsorise_and_scale(df_yr['pat_cagr_5yr'])
        
        de_s = df_yr['debt_to_equity'].apply(score_de)
        icr_s = df_yr['interest_coverage'].apply(score_icr)
        
        profitability = 0.15 * roe_s + 0.10 * roce_s + 0.10 * npm_s
        cash_quality = 0.15 * fcf_cagr_s + 0.10 * cfo_pat_s + 0.05 * fcf_flag_s
        growth = 0.10 * rev_cagr_s + 0.10 * pat_cagr_s
        leverage = 0.10 * de_s + 0.05 * icr_s
        
        composite = profitability + cash_quality + growth + leverage
        df_calc.loc[idx_yr, 'composite_quality_score'] = composite
        
    # 5. Write back to database
    logger.info(f"Upserting {len(df_calc)} calculated rows back into financial_ratios...")
    cursor = conn.cursor()
    
    for idx, row in df_calc.iterrows():
        cursor.execute("""
            UPDATE financial_ratios
            SET net_profit_margin_pct = ?,
                operating_profit_margin_pct = ?,
                return_on_equity_pct = ?,
                return_on_capital_employed_pct = ?,
                debt_to_equity = ?,
                interest_coverage = ?,
                asset_turnover = ?,
                free_cash_flow_cr = ?,
                capex_cr = ?,
                earnings_per_share = ?,
                book_value_per_share = ?,
                dividend_payout_ratio_pct = ?,
                total_debt_cr = ?,
                cash_from_operations_cr = ?,
                revenue_cagr_5yr = ?,
                pat_cagr_5yr = ?,
                eps_cagr_5yr = ?,
                sales_cagr_3yr = ?,
                sales_cagr_5yr = ?,
                sales_cagr_10yr = ?,
                pat_cagr_3yr = ?,
                pat_cagr_10yr = ?,
                eps_cagr_3yr = ?,
                eps_cagr_10yr = ?,
                composite_quality_score = ?
            WHERE company_id = ? AND year = ?
        """, (
            row['net_profit_margin_pct'],
            row['operating_profit_margin_pct'],
            row['return_on_equity_pct'],
            row['return_on_capital_employed_pct'],
            row['debt_to_equity'],
            row['interest_coverage'],
            row['asset_turnover'],
            row['free_cash_flow_cr'],
            row['capex_cr'],
            row['earnings_per_share'],
            row['book_value_per_share'],
            row['dividend_payout_ratio_pct'],
            row['total_debt_cr'],
            row['cash_from_operations_cr'],
            row['revenue_cagr_5yr'],
            row['pat_cagr_5yr'],
            row['eps_cagr_5yr'],
            row['sales_cagr_3yr'],
            row['sales_cagr_5yr'],
            row['sales_cagr_10yr'],
            row['pat_cagr_3yr'],
            row['pat_cagr_10yr'],
            row['eps_cagr_3yr'],
            row['eps_cagr_10yr'],
            row['composite_quality_score'],
            row['company_id'],
            row['year']
        ))
        
    conn.commit()
    conn.close()
    logger.info("Master ratio engine run complete successfully.")

if __name__ == "__main__":
    run_master_engine()
