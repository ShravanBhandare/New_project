import sqlite3
import pandas as pd
import numpy as np
import os
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

DB_PATH = "data/nifty100.db"

def run_valuation_module():
    logger.info("Running Valuation & Market Data Module...")
    conn = sqlite3.connect(DB_PATH)
    
    # 1. Fetch companies, sectors, and ratios
    # Latest ratios and multiples
    query = """
    SELECT 
        c.id as company_id, c.company_name, s.broad_sector as sector,
        f.return_on_equity_pct as roe, f.net_profit_margin_pct as npm,
        f.free_cash_flow_cr as fcf, f.year
    FROM companies c
    JOIN sectors s ON c.id = s.company_id
    JOIN financial_ratios f ON c.id = f.company_id
    WHERE f.year = (SELECT MAX(year) FROM financial_ratios WHERE company_id = c.id)
    """
    latest_ratios = pd.read_sql(query, conn)
    
    # Fetch latest market multiples (year 2024 or latest year in market_cap)
    mc_query = """
    SELECT 
        m.company_id, m.year, m.market_cap_crore, m.enterprise_value_crore,
        m.pe_ratio, m.pb_ratio, m.ev_ebitda, m.dividend_yield_pct
    FROM market_cap m
    WHERE m.year = (SELECT MAX(year) FROM market_cap WHERE company_id = m.company_id)
    """
    latest_multiples = pd.read_sql(mc_query, conn)
    
    # Join the data
    val_df = pd.merge(latest_ratios, latest_multiples, on='company_id', how='inner')
    
    # FCF Yield = FCF / Market Cap * 100
    val_df['fcf_yield_pct'] = (val_df['fcf'] / val_df['market_cap_crore'] * 100.0).fillna(0.0)
    
    # Calculate 5-year median multiples for each company
    hist_multiples_query = """
    SELECT company_id, pe_ratio, pb_ratio, ev_ebitda
    FROM market_cap
    WHERE year >= 2020 -- last 5 years
    """
    hist_df = pd.read_sql(hist_multiples_query, conn)
    
    # Calculate medians
    medians = hist_df.groupby('company_id').median().reset_index()
    medians.columns = ['company_id', 'pe_5yr_median', 'pb_5yr_median', 'ev_ebitda_5yr_median']
    
    # Merge medians
    val_df = pd.merge(val_df, medians, on='company_id', how='left')
    
    # Calculate sector medians for latest year multiples
    sector_medians = val_df.groupby('sector')[['pe_ratio', 'pb_ratio', 'ev_ebitda']].median().reset_index()
    sector_medians.columns = ['sector', 'sector_pe_median', 'sector_pb_median', 'sector_ev_ebitda_median']
    
    # Merge sector medians
    val_df = pd.merge(val_df, sector_medians, on='sector', how='left')
    
    # Apply Overvaluation / Discount flags
    # P/E > (sector_median * 1.5) -> 'Caution'
    # P/E < (sector_median * 0.7) -> 'Discount'
    # Otherwise -> 'Fair Value'
    flags = []
    
    for idx, row in val_df.iterrows():
        comp = row['company_id']
        pe = row['pe_ratio']
        sec_pe = row['sector_pe_median']
        
        if pd.isna(pe) or pd.isna(sec_pe) or pe <= 0 or sec_pe <= 0:
            flags.append(('Fair Value', 'No multiple available for sector benchmark'))
            continue
            
        if pe > (sec_pe * 1.5):
            flags.append(('Caution', f"P/E ({pe:.1f}x) is over 1.5x sector median ({sec_pe:.1f}x)"))
        elif pe < (sec_pe * 0.7):
            flags.append(('Discount', f"P/E ({pe:.1f}x) is under 0.7x sector median ({sec_pe:.1f}x)"))
        else:
            flags.append(('Fair Value', f"P/E ({pe:.1f}x) is in line with sector median ({sec_pe:.1f}x)"))
            
    val_df['valuation_flag'] = [f[0] for f in flags]
    val_df['rationale'] = [f[1] for f in flags]
    
    # Save valuation_summary.xlsx
    summary_cols = [
        'company_id', 'company_name', 'sector', 'pe_ratio', 'pe_5yr_median', 'sector_pe_median',
        'pb_ratio', 'pb_5yr_median', 'sector_pb_median', 'ev_ebitda', 'ev_ebitda_5yr_median',
        'sector_ev_ebitda_median', 'dividend_yield_pct', 'fcf_yield_pct', 'valuation_flag'
    ]
    
    os.makedirs("output", exist_ok=True)
    summary_df = val_df[summary_cols].copy()
    # Round
    for col in summary_df.select_dtypes(include=[np.number]).columns:
        summary_df[col] = summary_df[col].round(2)
        
    summary_path = "output/valuation_summary.xlsx"
    summary_df.to_excel(summary_path, sheet_name="Valuation Summary", index=False)
    logger.info(f"Valuation summary exported to {summary_path}")
    
    # Save valuation_flags.csv (only Caution and Discount flags)
    flags_df = val_df[val_df['valuation_flag'].isin(['Caution', 'Discount'])][
        ['company_id', 'company_name', 'sector', 'pe_ratio', 'sector_pe_median', 'valuation_flag', 'rationale']
    ].copy()
    
    flags_path = "output/valuation_flags.csv"
    flags_df.to_csv(flags_path, index=False)
    logger.info(f"Valuation flags exported to {flags_path}")
    
    conn.close()

if __name__ == "__main__":
    run_valuation_module()
