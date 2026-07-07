import sqlite3
import pandas as pd
import numpy as np
import yaml
import os
import logging
from typing import List, Dict, Any, Tuple

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = "data/nifty100.db"
CONFIG_PATH = "config/screener_config.yaml"

def get_screener_data(active_year: str = '2024-03') -> pd.DataFrame:
    """
    Fetch financial ratios and join with company info, sector, and market cap
    for the specified active year.
    """
    if not os.path.exists(DB_PATH):
        logger.error(f"Database file not found at {DB_PATH}.")
        return pd.DataFrame()

    conn = sqlite3.connect(DB_PATH)
    
    # 1. Fetch companies
    df_comp = pd.read_sql("SELECT id as company_id, company_name FROM companies", conn)
    
    # 2. Fetch sectors
    df_sec = pd.read_sql("SELECT company_id, broad_sector as sector, sub_sector FROM sectors", conn)
    
    # 3. Fetch financial ratios for active year
    df_fr = pd.read_sql("SELECT * FROM financial_ratios WHERE year = ?", conn, params=(active_year,))
    if df_fr.empty:
        logger.warning(f"No records found in financial_ratios for active year {active_year}")
        conn.close()
        return pd.DataFrame()
        
    # Get previous year D/E to compute de_declining
    try:
        parts = active_year.split('-')
        prev_year = f"{int(parts[0]) - 1}-{parts[1]}"
    except:
        prev_year = None

    if prev_year:
        df_prev_de = pd.read_sql("SELECT company_id, debt_to_equity as prev_debt_to_equity FROM financial_ratios WHERE year = ?", conn, params=(prev_year,))
    else:
        df_prev_de = pd.DataFrame(columns=['company_id', 'prev_debt_to_equity'])

    # 4. Fetch market cap and valuation multiples
    # Parse integer year from active_year string (e.g. '2024-03' -> 2024)
    try:
        yr_val = int(active_year.split('-')[0])
    except:
        yr_val = 2024
        
    df_mc = pd.read_sql("SELECT company_id, market_cap_crore, pe_ratio, pb_ratio, ev_ebitda, dividend_yield_pct FROM market_cap WHERE year = ?", conn, params=(yr_val,))
    
    # 5. Fetch profit and loss to get sales
    df_pl = pd.read_sql("SELECT company_id, sales, net_profit FROM profitandloss WHERE year = ?", conn, params=(active_year,))
    
    conn.close()
    
    # Merge dataframes
    df = df_fr.merge(df_comp, on='company_id', how='inner')
    df = df.merge(df_sec, on='company_id', how='left')
    df = df.merge(df_mc, on='company_id', how='left')
    df = df.merge(df_pl, on='company_id', how='left', suffixes=('', '_pl'))
    df = df.merge(df_prev_de, on='company_id', how='left')
    
    # Fill sales and net_profit if missing in ratios but present in P&L
    if 'sales' not in df.columns:
        df['sales'] = df['sales_pl'] if 'sales_pl' in df.columns else np.nan
    else:
        df['sales'] = df['sales'].fillna(df['sales_pl']) if 'sales_pl' in df.columns else df['sales']
        
    # Calculate FCF Yield = free_cash_flow_cr / market_cap_crore * 100
    def calc_fcf_yield(row):
        fcf = row.get('free_cash_flow_cr')
        mc = row.get('market_cap_crore')
        if pd.isna(fcf) or pd.isna(mc) or mc <= 0:
            return 0.0
        return (fcf / mc) * 100.0
        
    df['fcf_yield'] = df.apply(calc_fcf_yield, axis=1)
    
    # Calculate de_declining
    def check_de_declining(row):
        de = row.get('debt_to_equity')
        prev_de = row.get('prev_debt_to_equity')
        if pd.isna(de) or pd.isna(prev_de):
            return False
        return de < prev_de
        
    df['de_declining'] = df.apply(check_de_declining, axis=1)
    
    # Round debt_to_equity to 2 decimal places to enable "D/E == 0" for virtually debt-free companies
    if 'debt_to_equity' in df.columns:
        df['debt_to_equity'] = df['debt_to_equity'].round(2)
        
    return df


def apply_preset_filters(df: pd.DataFrame, preset_name: str, config: dict) -> pd.DataFrame:
    """
    Filter the master screener DataFrame based on preset rules using pandas query.
    """
    preset = config['presets'].get(preset_name)
    if not preset:
        logger.error(f"Preset {preset_name} not found in config.")
        return pd.DataFrame()
        
    filtered_df = df.copy()
    query_parts = []
    
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
        'sales': 'sales',
        'composite_score': 'composite_quality_score',
        'de_declining': 'de_declining'
    }
    
    for rule in preset['filters']:
        col = rule['metric']
        op = rule['operator']
        val = rule['value']
        
        df_col = col_map.get(col, col)
        
        # Build query part
        if op == "==":
            query_parts.append(f"{df_col} == {val}")
        else:
            query_parts.append(f"{df_col} {op} {val}")
            
    if query_parts:
        query_str = " and ".join(query_parts)
        logger.info(f"Preset '{preset_name}' - applying query: {query_str}")
        try:
            filtered_df = filtered_df.query(query_str)
        except Exception as e:
            logger.error(f"Failed to run query '{query_str}': {e}")
            # Fallback to manual filter if query fails
            for rule in preset['filters']:
                col = rule['metric']
                op = rule['operator']
                val = rule['value']
                df_col = col_map.get(col, col)
                if df_col not in filtered_df.columns:
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
    rank_metric = preset.get('ranking_metric', 'composite_quality_score')
    rank_col = col_map.get(rank_metric, rank_metric)
    ascending = preset.get('sort_order', 'desc') == 'asc'
    
    if rank_col in filtered_df.columns:
        filtered_df = filtered_df.sort_values(by=rank_col, ascending=ascending)
        
    return filtered_df

def run_screener_and_export(active_year: str = '2024-03'):
    """
    Run screener presets and export results into output/screener_output.xlsx.
    """
    logger.info(f"Running custom filter engine for active year: {active_year}...")
    
    if not os.path.exists(CONFIG_PATH):
        logger.error(f"Config file {CONFIG_PATH} does not exist.")
        return
        
    with open(CONFIG_PATH, 'r') as f:
        config = yaml.safe_load(f)
        
    df = get_screener_data(active_year)
    if df.empty:
        logger.error("No screener data loaded.")
        return
        
    logger.info(f"Loaded master screener data with {len(df)} records.")
    
    output_path = "output/screener_output.xlsx"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        for preset_name in config['presets'].keys():
            preset_df = apply_preset_filters(df, preset_name, config)
            sheet_name = preset_name.replace('_', ' ').title()
            
            display_cols = [
                'company_id', 'company_name', 'sector', 'return_on_equity_pct',
                'debt_to_equity', 'free_cash_flow_cr', 'pe_ratio', 'dividend_yield_pct',
                'sales_cagr_5yr', 'pat_cagr_5yr', 'composite_quality_score', 'fcf_yield',
                'sales_cagr_3yr', 'de_declining', 'sales'
            ]
            
            # Ensure columns exist
            cols_to_use = [c for c in display_cols if c in preset_df.columns]
            output_df = preset_df[cols_to_use].copy()
            
            # Round numeric columns
            for col in output_df.select_dtypes(include=[np.number]).columns:
                output_df[col] = output_df[col].round(2)
                
            output_df.to_excel(writer, sheet_name=sheet_name, index=False)
            logger.info(f"Preset sheet '{sheet_name}' populated with {len(output_df)} matches.")
            
    logger.info(f"Screener presets exported successfully to {output_path}.")


if __name__ == "__main__":
    run_screener_and_export()
