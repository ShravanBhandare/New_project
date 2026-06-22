import sqlite3
import pandas as pd
import numpy as np
import yaml
import os
import logging
from typing import List, Dict, Any, Tuple
from src.analytics.cagr import calculate_cagr

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

DB_PATH = "data/nifty100.db"
CONFIG_PATH = "config/screener_config.yaml"

def winsorise_and_scale(series: pd.Series) -> pd.Series:
    """Cap series values at P10 and P90, then scale linearly to [0, 100]."""
    if series.empty:
        return series
        
    p10 = series.quantile(0.10)
    p90 = series.quantile(0.90)
    
    capped = series.clip(lower=p10, upper=p90)
    
    if p90 == p10:
        return pd.Series(100.0, index=series.index)
        
    scaled = ((capped - p10) / (p90 - p10)) * 100.0
    return scaled

def score_de(de_val: float) -> float:
    """Calculate D/E score based on spec mapping: 0=100, 0.5=85, 1=70, 2=50, >5=0."""
    if pd.isna(de_val) or de_val < 0:
        return 0.0
    if de_val == 0:
        return 100.0
    elif de_val <= 0.5:
        # Interpolate between 100 and 85
        return 100.0 - (de_val / 0.5) * 15.0
    elif de_val <= 1.0:
        # Interpolate between 85 and 70
        return 85.0 - ((de_val - 0.5) / 0.5) * 15.0
    elif de_val <= 2.0:
        # Interpolate between 70 and 50
        return 70.0 - ((de_val - 1.0) / 1.0) * 20.0
    elif de_val <= 5.0:
        # Interpolate between 50 and 0
        return 50.0 - ((de_val - 2.0) / 3.0) * 50.0
    else:
        return 0.0

def score_icr(icr_val: float) -> float:
    """Calculate ICR score based on spec mapping: >10=100, 5=75, 3=50, <1.5=0."""
    if pd.isna(icr_val):
        return 0.0
    if icr_val >= 10.0:
        return 100.0
    elif icr_val >= 5.0:
        # Interpolate between 75 and 100
        return 75.0 + ((icr_val - 5.0) / 5.0) * 25.0
    elif icr_val >= 3.0:
        # Interpolate between 50 and 75
        return 50.0 + ((icr_val - 3.0) / 2.0) * 25.0
    elif icr_val >= 1.5:
        # Interpolate between 0 and 50
        return 0.0 + ((icr_val - 1.5) / 1.5) * 50.0
    else:
        return 0.0

def get_latest_screener_data() -> pd.DataFrame:
    """
    Fetch and compute metrics for the latest financial year for all companies.
    Computes 5-year CAGRs, FCF, OPM, ROE, etc.
    """
    conn = sqlite3.connect(DB_PATH)
    
    # 1. Fetch companies info
    comp_df = pd.read_sql("SELECT id, company_name FROM companies", conn)
    
    # 2. Get latest year per company from financial_ratios table
    latest_years = pd.read_sql("SELECT company_id, MAX(year) as latest_year FROM financial_ratios GROUP BY company_id", conn)
    
    # Fetch all P&L and BS history to compute CAGRs
    pl_hist = pd.read_sql("SELECT company_id, year, sales, net_profit, eps FROM profitandloss ORDER BY company_id, year", conn)
    cf_hist = pd.read_sql("SELECT company_id, year, operating_activity, investing_activity FROM cashflow ORDER BY company_id, year", conn)
    mc_hist = pd.read_sql("SELECT company_id, year, market_cap_crore, pe_ratio, pb_ratio, ev_ebitda, dividend_yield_pct FROM market_cap ORDER BY company_id, year", conn)
    
    # Map from history for CAGR calculations
    # Let's pivot P&L by year to easily look back 3 and 5 years
    pl_pivot = pl_hist.set_index(['company_id', 'year'])
    cf_pivot = cf_hist.set_index(['company_id', 'year'])
    
    # We will build a list of records for the latest year of each company
    records = []
    
    for idx, row in latest_years.iterrows():
        comp_id = row['company_id']
        ly = row['latest_year']
        
        # Parse year string (e.g. 2024-03)
        try:
            ly_yr = int(ly.split('-')[0])
            ly_mo = ly.split('-')[1]
        except:
            continue
            
        # Get historical values for CAGR
        def get_val(df_pivot, col, yr):
            yr_str = f"{yr}-{ly_mo}"
            if (comp_id, yr_str) in df_pivot.index:
                return df_pivot.loc[(comp_id, yr_str), col]
            return None
            
        sales_t = get_val(pl_pivot, 'sales', ly_yr)
        sales_t3 = get_val(pl_pivot, 'sales', ly_yr - 3)
        sales_t5 = get_val(pl_pivot, 'sales', ly_yr - 5)
        
        net_profit_t = get_val(pl_pivot, 'net_profit', ly_yr)
        net_profit_t5 = get_val(pl_pivot, 'net_profit', ly_yr - 5)
        
        eps_t = get_val(pl_pivot, 'eps', ly_yr)
        eps_t5 = get_val(pl_pivot, 'eps', ly_yr - 5)
        
        # CFO and FCF history
        cfo_t = get_val(cf_pivot, 'operating_activity', ly_yr)
        cfo_history = []
        pat_history = []
        fcf_t = None
        fcf_t5 = None
        
        for offset in range(6):
            c_yr = ly_yr - offset
            c_cfo = get_val(cf_pivot, 'operating_activity', c_yr)
            c_cfi = get_val(cf_pivot, 'investing_activity', c_yr)
            c_pat = get_val(pl_pivot, 'net_profit', c_yr)
            if c_cfo is not None:
                cfo_history.append(c_cfo)
            if c_pat is not None:
                pat_history.append(c_pat)
            if offset == 0 and c_cfo is not None and c_cfi is not None:
                fcf_t = c_cfo + c_cfi
            if offset == 5 and c_cfo is not None and c_cfi is not None:
                fcf_t5 = c_cfo + c_cfi
                
        # Calculate CAGRs
        def cagr_val(base, end, n):
            val, flag, _ = calculate_cagr(base if base is not None else 0.0, end if end is not None else 0.0, n)
            return val if flag is None else 0.0
            
        sales_cagr_3yr = cagr_val(sales_t3, sales_t, 3)
        sales_cagr_5yr = cagr_val(sales_t5, sales_t, 5)
        pat_cagr_5yr = cagr_val(net_profit_t5, net_profit_t, 5)
        fcf_cagr_5yr = cagr_val(fcf_t5, fcf_t, 5)
        
        # CFO/PAT ratio
        cfo_pat_ratio = (cfo_t / net_profit_t) if (cfo_t is not None and net_profit_t is not None and net_profit_t != 0) else 0.0
        
        # Fetch current ratios for this latest year
        ratios_df = pd.read_sql("SELECT * FROM financial_ratios WHERE company_id = ? AND year = ?", conn, params=(comp_id, ly))
        if ratios_df.empty:
            continue
            
        r_row = ratios_df.iloc[0]
        
        # Fetch valuation multiples for latest year
        # Find year int like 2024
        mc_df = pd.read_sql("SELECT * FROM market_cap WHERE company_id = ? AND year = ?", conn, params=(comp_id, ly_yr))
        if not mc_df.empty:
            m_row = mc_df.iloc[0]
            pe = m_row.get('pe_ratio')
            pb = m_row.get('pb_ratio')
            ev_ebitda = m_row.get('ev_ebitda')
            div_yield = m_row.get('dividend_yield_pct')
        else:
            pe = None
            pb = None
            ev_ebitda = None
            div_yield = 0.0
            
        # Fetch sector mapping
        sec_df = pd.read_sql("SELECT broad_sector, sub_sector FROM sectors WHERE company_id = ?", conn, params=(comp_id,))
        if not sec_df.empty:
            sector = sec_df.iloc[0]['broad_sector']
            sub_sector = sec_df.iloc[0]['sub_sector']
        else:
            sector = "Other"
            sub_sector = "Other"
            
        records.append({
            'company_id': comp_id,
            'company_name': comp_df[comp_df['id'] == comp_id].iloc[0]['company_name'],
            'year': ly,
            'sector': sector,
            'sub_sector': sub_sector,
            'sales': r_row['sales'] if 'sales' in r_row else sales_t, # use sales_t if missing
            'net_profit': net_profit_t,
            'return_on_equity_pct': r_row['return_on_equity_pct'] if r_row['return_on_equity_pct'] is not None else 0.0,
            'roce_percentage': r_row['roce_percentage'] if 'roce_percentage' in r_row and r_row['roce_percentage'] is not None else 0.0, # wait, we store ROCE in financial_ratios or check?
            'net_profit_margin_pct': r_row['net_profit_margin_pct'] if r_row['net_profit_margin_pct'] is not None else 0.0,
            'debt_to_equity': r_row['debt_to_equity'] if r_row['debt_to_equity'] is not None else 0.0,
            'interest_coverage': r_row['interest_coverage'] if r_row['interest_coverage'] is not None else 999.0,
            'free_cash_flow_cr': r_row['free_cash_flow_cr'] if r_row['free_cash_flow_cr'] is not None else 0.0,
            'capex_cr': r_row['capex_cr'] if r_row['capex_cr'] is not None else 0.0,
            'dividend_payout_ratio_pct': r_row['dividend_payout_ratio_pct'] if r_row['dividend_payout_ratio_pct'] is not None else 0.0,
            'pe_ratio': pe,
            'pb_ratio': pb,
            'ev_ebitda': ev_ebitda,
            'dividend_yield_pct': div_yield if div_yield is not None else 0.0,
            'sales_cagr_3yr': sales_cagr_3yr,
            'sales_cagr_5yr': sales_cagr_5yr,
            'pat_cagr_5yr': pat_cagr_5yr,
            'fcf_cagr_5yr': fcf_cagr_5yr,
            'cfo_pat_ratio': cfo_pat_ratio
        })
        
    conn.close()
    
    screener_df = pd.DataFrame(records)
    
    # Let's compute ROCE dynamically if not in columns
    # We will use Return on Equity as proxy if roce_percentage is missing
    if 'roce_percentage' not in screener_df.columns or screener_df['roce_percentage'].sum() == 0:
        screener_df['roce_percentage'] = screener_df['return_on_equity_pct']
        
    # Calculate Winsorised and Scaled scores for Composite Scoring
    # Profitability (35%): ROE (15%), ROCE (10%), NPM (10%)
    roe_score = winsorise_and_scale(screener_df['return_on_equity_pct'])
    roce_score = winsorise_and_scale(screener_df['roce_percentage'])
    npm_score = winsorise_and_scale(screener_df['net_profit_margin_pct'])
    
    # Cash Quality (30%): FCF CAGR 5yr (15%), CFO/PAT (10%), FCF > 0 flag (5%)
    fcf_cagr_score = winsorise_and_scale(screener_df['fcf_cagr_5yr'])
    cfo_pat_score = winsorise_and_scale(screener_df['cfo_pat_ratio'])
    fcf_flag_score = screener_df['free_cash_flow_cr'].apply(lambda x: 100.0 if x > 0 else 0.0)
    
    # Growth (20%): Revenue CAGR 5yr (10%), PAT CAGR 5yr (10%)
    rev_cagr_score = winsorise_and_scale(screener_df['sales_cagr_5yr'])
    pat_cagr_score = winsorise_and_scale(screener_df['pat_cagr_5yr'])
    
    # Leverage (15%): D/E (10%), ICR (5%)
    de_score = screener_df['debt_to_equity'].apply(score_de)
    icr_score = screener_df['interest_coverage'].apply(score_icr)
    
    # Combine scores
    profitability = 0.15 * roe_score + 0.10 * roce_score + 0.10 * npm_score
    cash_quality = 0.15 * fcf_cagr_score + 0.10 * cfo_pat_score + 0.05 * fcf_flag_score
    growth = 0.10 * rev_cagr_score + 0.10 * pat_cagr_score
    leverage = 0.10 * de_score + 0.05 * icr_score
    
    screener_df['composite_score'] = profitability + cash_quality + growth + leverage
    
    # Calculate FCF Yield
    # FCF Yield = FCF / Market Cap * 100. Let's fetch latest market cap.
    latest_mc_query = "SELECT company_id, market_cap_crore FROM market_cap WHERE year = 2024"
    conn = sqlite3.connect(DB_PATH)
    latest_mc = pd.read_sql(latest_mc_query, conn)
    conn.close()
    
    mc_map = dict(zip(latest_mc['company_id'], latest_mc['market_cap_crore']))
    
    def calc_fcf_yield(row):
        comp = row['company_id']
        fcf = row['free_cash_flow_cr']
        mc = mc_map.get(comp, 0.0)
        if mc > 0:
            return (fcf / mc) * 100.0
        return 0.0
        
    screener_df['fcf_yield'] = screener_df.apply(calc_fcf_yield, axis=1)
    
    return screener_df

def apply_preset_filters(df: pd.DataFrame, preset_name: str, config: dict) -> pd.DataFrame:
    """Filter the master screener DataFrame based on preset rules."""
    preset = config['presets'].get(preset_name)
    if not preset:
        logger.error(f"Preset {preset_name} not found in config.")
        return pd.DataFrame()
        
    filtered_df = df.copy()
    
    # Apply each filter in preset
    for rule in preset['filters']:
        col = rule['metric']
        op = rule['operator']
        val = rule['value']
        
        # Replace mapping to match dataframe columns
        col_map = {
            'return_on_equity_pct': 'return_on_equity_pct',
            'debt_to_equity': 'debt_to_equity',
            'free_cash_flow_cr': 'free_cash_flow_cr',
            'sales_cagr_5yr': 'sales_cagr_5yr',
            'sales_cagr_3yr': 'sales_cagr_3yr',
            'pe_ratio': 'pe_ratio',
            'pb_ratio': 'pb_ratio',
            'dividend_yield_pct': 'dividend_yield_pct',
            'dividend_payout_ratio_pct': 'dividend_payout_ratio_pct',
            'pat_cagr_5yr': 'pat_cagr_5yr',
            'sales': 'sales'
        }
        
        df_col = col_map.get(col, col)
        if df_col not in filtered_df.columns:
            logger.warning(f"Column {df_col} not found for filter rule.")
            continue
            
        if op == ">":
            filtered_df = filtered_df[filtered_df[df_col] > val]
        elif op == "<":
            filtered_df = filtered_df[filtered_df[df_col] < val]
        elif op == "==":
            filtered_df = filtered_df[filtered_df[df_col] == val]
        elif op == ">=":
            filtered_df = filtered_df[filtered_df[df_col] >= val]
        elif op == "<=":
            filtered_df = filtered_df[filtered_df[df_col] <= val]
            
    # Sort and rank
    rank_col = col_map.get(preset['ranking_metric'], preset['ranking_metric'])
    ascending = preset['sort_order'] == "asc"
    
    filtered_df = filtered_df.sort_values(by=rank_col, ascending=ascending)
    return filtered_df

def run_screener_and_export():
    """Load config, run all 6 screener presets, and export them into sheets of screener_output.xlsx."""
    logger.info("Running screener engine...")
    
    if not os.path.exists(CONFIG_PATH):
        logger.error(f"Config file {CONFIG_PATH} does not exist.")
        return
        
    with open(CONFIG_PATH, 'r') as f:
        config = yaml.safe_load(f)
        
    df = get_latest_screener_data()
    logger.info(f"Loaded master screener data with {len(df)} companies.")
    
    output_path = "output/screener_output.xlsx"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # We will write to multiple Excel sheets
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        for preset_name in config['presets'].keys():
            preset_df = apply_preset_filters(df, preset_name, config)
            # clean sheet name
            sheet_name = preset_name.replace('_', ' ').title()
            # Select key columns to display in output
            display_cols = [
                'company_id', 'company_name', 'sector', 'return_on_equity_pct',
                'debt_to_equity', 'free_cash_flow_cr', 'pe_ratio', 'dividend_yield_pct',
                'sales_cagr_5yr', 'pat_cagr_5yr', 'composite_score', 'fcf_yield'
            ]
            # Ensure columns exist
            cols_to_use = [c for c in display_cols if c in preset_df.columns]
            
            output_df = preset_df[cols_to_use].copy()
            # Round numeric columns for premium formatting
            for col in output_df.select_dtypes(include=[np.number]).columns:
                output_df[col] = output_df[col].round(2)
                
            output_df.to_excel(writer, sheet_name=sheet_name, index=False)
            logger.info(f"Sheet '{sheet_name}' populated with {len(output_df)} matching companies.")
            
    logger.info(f"Screener presets exported successfully to {output_path}.")

if __name__ == "__main__":
    run_screener_and_export()
