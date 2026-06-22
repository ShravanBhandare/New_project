import re
import logging
import pandas as pd
import requests
import concurrent.futures
from typing import List, Dict, Any, Tuple, Set

logger = logging.getLogger(__name__)

def log_failure(failures: List[Dict[str, Any]], company_id: str, year: str, field: str, issue: str, severity: str):
    """Utility to append a validation failure."""
    failures.append({
        'company_id': company_id,
        'year': year,
        'field': field,
        'issue': issue,
        'severity': severity
    })
    msg = f"[{severity}] Company: {company_id}, Year: {year}, Field: {field} -> {issue}"
    if severity == 'CRITICAL':
        logger.error(msg)
    elif severity == 'WARNING':
        logger.warning(msg)
    else:
        logger.info(msg)

def validate_companies_sheet(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
    """Validate companies master sheet. Enforces DQ-01 and DQ-08."""
    failures = []
    valid_rows = []
    
    # DQ-01: Company PK Uniqueness
    seen_ids = set()
    
    for idx, row in df.iterrows():
        comp_id = row.get('id')
        if pd.isna(comp_id):
            log_failure(failures, 'MISSING', 'N/A', 'id', 'Missing company ID', 'CRITICAL')
            continue
            
        comp_id_str = str(comp_id).strip().upper()
        
        # DQ-08: Ticker Format Length (2-12 chars)
        if not (2 <= len(comp_id_str) <= 12):
            log_failure(failures, comp_id_str, 'N/A', 'id', f'Ticker length {len(comp_id_str)} out of range (2-12)', 'CRITICAL')
            continue
            
        if comp_id_str in seen_ids:
            log_failure(failures, comp_id_str, 'N/A', 'id', 'Duplicate company ticker (DQ-01)', 'CRITICAL')
            continue
            
        seen_ids.add(comp_id_str)
        # Update row with normalised values
        row_dict = row.to_dict()
        row_dict['id'] = comp_id_str
        
        # Clean company name: strip \n
        c_name = row_dict.get('company_name')
        if isinstance(c_name, str):
            row_dict['company_name'] = c_name.replace('\n', ' ').strip()
            
        valid_rows.append(row_dict)
        
    return pd.DataFrame(valid_rows) if valid_rows else pd.DataFrame(columns=df.columns), failures

def validate_time_series_sheet(df: pd.DataFrame, sheet_name: str, valid_companies: Set[str]) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
    """
    Validate P&L, Balance Sheet, and Cash Flow sheets.
    Enforces DQ-02 (dedup), DQ-03 (FK), DQ-07 (Year), and DQ-08 (Ticker).
    """
    failures = []
    valid_rows = []
    
    # Track (company_id, year) for DQ-02
    seen_keys = set()
    # Keep rows for deduplication
    dedup_rows = {}
    
    # Sort or process rows in order. If duplicates occur, we keep the last one.
    for idx, row in df.iterrows():
        comp_id = row.get('company_id')
        year_val = row.get('year')
        
        if pd.isna(comp_id):
            log_failure(failures, 'MISSING', str(year_val), 'company_id', f'Missing company_id in {sheet_name}', 'CRITICAL')
            continue
            
        comp_id_str = str(comp_id).strip().upper()
        
        # DQ-08: Ticker Format Length
        if not (2 <= len(comp_id_str) <= 12):
            log_failure(failures, comp_id_str, str(year_val), 'company_id', f'Ticker length {len(comp_id_str)} out of range (2-12)', 'CRITICAL')
            continue
            
        # DQ-03: FK Integrity
        if comp_id_str not in valid_companies:
            log_failure(failures, comp_id_str, str(year_val), 'company_id', f'Foreign Key violation: {comp_id_str} not in companies master', 'CRITICAL')
            continue
            
        # DQ-07: Year Format
        from src.etl.normaliser import normalize_year
        norm_yr = normalize_year(year_val)
        if norm_yr == "PARSE_ERROR":
            log_failure(failures, comp_id_str, str(year_val), 'year', f'Unparseable year label: {year_val}', 'CRITICAL')
            continue
            
        row_dict = row.to_dict()
        row_dict['company_id'] = comp_id_str
        row_dict['year'] = norm_yr
        
        key = (comp_id_str, norm_yr)
        if key in seen_keys:
            log_failure(failures, comp_id_str, norm_yr, 'company_id+year', f'Duplicate entry found in {sheet_name} (DQ-02). Keeping last occurrence.', 'WARNING')
            
        seen_keys.add(key)
        dedup_rows[key] = row_dict
        
    return pd.DataFrame(list(dedup_rows.values())) if dedup_rows else pd.DataFrame(columns=df.columns), failures

def validate_pl_business_rules(df: pd.DataFrame, non_financial_companies: Set[str]) -> List[Dict[str, Any]]:
    """Enforces DQ-05, DQ-06, DQ-11, DQ-12, DQ-14."""
    failures = []
    for idx, row in df.iterrows():
        comp_id = row['company_id']
        year = row['year']
        sales = row.get('sales', 0)
        expenses = row.get('expenses', 0)
        op_profit = row.get('operating_profit', 0)
        opm = row.get('opm_percentage', 0)
        tax_pct = row.get('tax_percentage', 0)
        div_payout = row.get('dividend_payout', 0)
        net_profit = row.get('net_profit', 0)
        eps = row.get('eps', 0)
        
        # DQ-06: Positive Sales for non-bank companies
        if comp_id in non_financial_companies:
            if sales <= 0:
                log_failure(failures, comp_id, year, 'sales', f'Sales value {sales} is non-positive for non-financial company (DQ-06)', 'WARNING')
                
        # DQ-05: OPM Cross-Check
        if sales > 0:
            calc_opm = (op_profit / sales) * 100
            if abs(opm - calc_opm) >= 1.0:
                log_failure(failures, comp_id, year, 'opm_percentage', f'OPM cross-check mismatch: sheet={opm}%, calc={calc_opm:.2f}% (DQ-05)', 'WARNING')
                
        # DQ-11: Tax Rate Range (0 to 60)
        if not pd.isna(tax_pct):
            if not (0 <= tax_pct <= 60):
                log_failure(failures, comp_id, year, 'tax_percentage', f'Tax percentage {tax_pct}% out of range [0, 60] (DQ-11)', 'WARNING')
                
        # DQ-12: Dividend Payout Cap (200%)
        if not pd.isna(div_payout):
            if div_payout > 200:
                log_failure(failures, comp_id, year, 'dividend_payout', f'Dividend payout {div_payout}% exceeds cap of 200% (DQ-12)', 'WARNING')
                
        # DQ-14: EPS Sign Consistency
        if not pd.isna(eps) and not pd.isna(net_profit):
            if net_profit > 0 and eps <= 0:
                log_failure(failures, comp_id, year, 'eps', f'Net profit is positive ({net_profit}) but EPS is non-positive ({eps}) (DQ-14)', 'WARNING')
                
    return failures

def validate_bs_business_rules(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Enforces DQ-04, DQ-10, DQ-15."""
    failures = []
    for idx, row in df.iterrows():
        comp_id = row['company_id']
        year = row['year']
        
        equity = row.get('equity_capital', 0)
        reserves = row.get('reserves', 0)
        borrowings = row.get('borrowings', 0)
        other_liab = row.get('other_liabilities', 0)
        total_liab = row.get('total_liabilities', 0)
        
        fixed_assets = row.get('fixed_assets', 0)
        cwip = row.get('cwip', 0)
        investments = row.get('investments', 0)
        other_asset = row.get('other_asset', 0)
        total_assets = row.get('total_assets', 0)
        
        # If NaN, treat as 0 for calculations
        equity = 0 if pd.isna(equity) else equity
        reserves = 0 if pd.isna(reserves) else reserves
        borrowings = 0 if pd.isna(borrowings) else borrowings
        other_liab = 0 if pd.isna(other_liab) else other_liab
        
        fixed_assets = 0 if pd.isna(fixed_assets) else fixed_assets
        cwip = 0 if pd.isna(cwip) else cwip
        investments = 0 if pd.isna(investments) else investments
        other_asset = 0 if pd.isna(other_asset) else other_asset
        
        calc_liab = equity + reserves + borrowings + other_liab
        calc_assets = fixed_assets + cwip + investments + other_asset
        
        # DQ-04: Balance Sheet Balance (within 1% of total_assets)
        if total_assets > 0:
            diff_assets_liab = abs(total_assets - total_liab) / total_assets
            if diff_assets_liab >= 0.01:
                log_failure(failures, comp_id, year, 'total_assets/total_liabilities', f'Balance sheet unbalanced: assets={total_assets}, liab={total_liab} (DQ-04)', 'WARNING')
                
        # DQ-10: Non-Negative Fixed Assets
        if not pd.isna(row.get('fixed_assets')) and row.get('fixed_assets') < 0:
            log_failure(failures, comp_id, year, 'fixed_assets', f'Fixed assets value {row.get("fixed_assets")} is negative. Coercing to 0. (DQ-10)', 'WARNING')
            df.at[idx, 'fixed_assets'] = 0.0
            
        # DQ-15: BSE/ASE Balance (ext.) (strict check total_assets == total_liabilities)
        if total_liab != total_assets:
            log_failure(failures, comp_id, year, 'total_assets/total_liabilities', f'Strict balance check mismatch: assets={total_assets}, liab={total_liab} (DQ-15)', 'INFO')
            
    return failures

def validate_cf_business_rules(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Enforces DQ-09."""
    failures = []
    for idx, row in df.iterrows():
        comp_id = row['company_id']
        year = row['year']
        
        cfo = row.get('operating_activity', 0)
        cfi = row.get('investing_activity', 0)
        cff = row.get('financing_activity', 0)
        ncf = row.get('net_cash_flow', 0)
        
        cfo = 0 if pd.isna(cfo) else cfo
        cfi = 0 if pd.isna(cfi) else cfi
        cff = 0 if pd.isna(cff) else cff
        
        calc_ncf = cfo + cfi + cff
        
        # DQ-09: Net Cash Check
        if abs(ncf - calc_ncf) > 10.0:
            log_failure(failures, comp_id, year, 'net_cash_flow', f'Net cash flow mismatch: sheet={ncf}, calculated={calc_ncf} (DQ-09)', 'WARNING')
            # Coerce to calculated if there's a major mismatch as per rule action
            df.at[idx, 'net_cash_flow'] = calc_ncf
            
    return failures

def validate_documents_sheet(df: pd.DataFrame, valid_companies: Set[str]) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
    """Validate documents and run DQ-13 (URL Check) in parallel after deduplication."""
    failures = []
    
    seen_keys = set()
    dedup_rows = {}
    
    for idx, row in df.iterrows():
        comp_id = row.get('company_id')
        year_val = row.get('Year')
        url = row.get('Annual_Report')
        
        if pd.isna(comp_id):
            continue
            
        comp_id_str = str(comp_id).strip().upper()
        if comp_id_str not in valid_companies:
            continue
            
        try:
            yr_int = int(year_val)
        except:
            continue
            
        row_dict = row.to_dict()
        row_dict['company_id'] = comp_id_str
        row_dict['Year'] = yr_int
        
        key = (comp_id_str, yr_int)
        if key in seen_keys:
            log_failure(failures, comp_id_str, str(yr_int), 'company_id+Year', f'Duplicate document link found in documents sheet (DQ-02). Keeping last occurrence.', 'WARNING')
        seen_keys.add(key)
        dedup_rows[key] = row_dict
        
    valid_rows = list(dedup_rows.values())
    rows_to_check = [(r['company_id'], r['Year'], r['Annual_Report']) for r in valid_rows]

    def check_url(item):
        comp_id_str, yr_int, url = item
        if isinstance(url, str) and url.startswith('http'):
            try:
                res = requests.head(url, timeout=0.5, allow_redirects=True)
                if res.status_code == 404:
                    return {
                        'company_id': comp_id_str, 'year': str(yr_int), 'field': 'Annual_Report',
                        'issue': f'URL returns 404: {url} (DQ-13)', 'severity': 'WARNING'
                    }
            except Exception as e:
                return {
                    'company_id': comp_id_str, 'year': str(yr_int), 'field': 'Annual_Report',
                    'issue': f'URL check failed with error: {e} (DQ-13)', 'severity': 'WARNING'
                }
        else:
            url_str = str(url)
            return {
                'company_id': comp_id_str, 'year': str(yr_int), 'field': 'Annual_Report',
                'issue': f'Invalid or missing URL: {url_str} (DQ-13)', 'severity': 'WARNING'
            }
        return None

    logger.info(f"Running URL validation check on {len(rows_to_check)} unique documents in parallel with ThreadPoolExecutor...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        results = list(executor.map(check_url, rows_to_check))
        for r in results:
            if r:
                failures.append(r)
                
    return pd.DataFrame(valid_rows) if valid_rows else pd.DataFrame(columns=df.columns), failures

def validate_coverage(time_series_dfs: List[pd.DataFrame]) -> List[Dict[str, Any]]:
    """Enforces DQ-16 (Coverage Check)."""
    failures = []
    comp_years = {}
    
    for df in time_series_dfs:
        if df.empty:
            continue
        for idx, row in df.iterrows():
            comp_id = row['company_id']
            yr = row['year']
            if comp_id not in comp_years:
                comp_years[comp_id] = set()
            comp_years[comp_id].add(yr)
            
    for comp_id, years in comp_years.items():
        if len(years) < 5:
            log_failure(failures, comp_id, 'ALL', 'records_count', f'Company has only {len(years)} years of records, expected >= 5 (DQ-16)', 'WARNING')
            
    return failures
