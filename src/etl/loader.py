import os
import sqlite3
import pandas as pd
import time
import logging
from datetime import datetime
from src.etl.normaliser import normalize_ticker, normalize_year
from src.etl.validator import (
    validate_companies_sheet,
    validate_time_series_sheet,
    validate_pl_business_rules,
    validate_bs_business_rules,
    validate_cf_business_rules,
    validate_documents_sheet,
    validate_coverage
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = "data/nifty100.db"
SCHEMA_PATH = "src/etl/schema.sql"

RAW_DIR = "data/raw"
SUPPORT_DIR = "data/supporting"

def init_db(conn: sqlite3.Connection):
    """Executes schema.sql to initialise SQLite database tables."""
    logger.info("Initializing database schema...")
    with open(SCHEMA_PATH, 'r') as f:
        schema_sql = f.read()
    conn.executescript(schema_sql)
    logger.info("Schema initialized successfully.")

def write_audit_log(audit_records: list):
    """Appends audit details to load_audit.csv."""
    audit_file = "load_audit.csv"
    df = pd.DataFrame(audit_records)
    if os.path.exists(audit_file):
        df.to_csv(audit_file, mode='a', header=False, index=False)
    else:
        df.to_csv(audit_file, index=False)
    logger.info(f"Audit log updated at {audit_file}.")

def write_failures_log(failures: list):
    """Writes all validation failures to validation_failures.csv."""
    failures_file = "validation_failures.csv"
    df = pd.DataFrame(failures)
    df.to_csv(failures_file, index=False)
    logger.info(f"Validation failures written to {failures_file}.")

def main():
    start_time = time.time()
    logger.info("Starting Nifty 100 ETL Ingestion Pipeline...")
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    # Connect to SQLite
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    init_db(conn)
    
    audit_records = []
    all_failures = []
    
    # Load Companies Master (Header=1)
    comp_path = os.path.join(RAW_DIR, "companies.xlsx")
    logger.info(f"Loading {comp_path}...")
    comp_df_raw = pd.read_excel(comp_path, header=1)
    
    # Validate Companies
    comp_df, comp_failures = validate_companies_sheet(comp_df_raw)
    all_failures.extend(comp_failures)
    
    # Insert companies to DB
    comp_df.to_sql("companies", conn, if_exists="append", index=False)
    valid_companies = set(comp_df['id'].tolist())
    
    rows_in = len(comp_df_raw)
    rows_out = len(comp_df)
    rejected = rows_in - rows_out
    audit_records.append({
        'table': 'companies',
        'rows_in': rows_in,
        'rows_out': rows_out,
        'rejected': rejected,
        'timestamp': datetime.now().isoformat(),
        'runtime_s': round(time.time() - start_time, 3)
    })
    logger.info(f"Loaded {rows_out} companies into database. Rejected {rejected} rows.")
    
    # Identify Financial Companies (Banks, NBFC, Life Insurance, Consumer Finance)
    # Load sectors mapping first to assist PL validation (banks check)
    sec_path = os.path.join(SUPPORT_DIR, "sectors.xlsx")
    logger.info(f"Loading {sec_path} for sector identification...")
    sec_df_raw = pd.read_excel(sec_path, header=0)
    
    # Clean sectors company ids
    sec_df_raw['company_id'] = sec_df_raw['company_id'].apply(normalize_ticker)
    # Keep only those matching valid companies
    sec_df = sec_df_raw[sec_df_raw['company_id'].isin(valid_companies)].copy()
    
    financial_sectors = ['Financials', 'Private Banks', 'Public Sector Banks', 'Life Insurance', 'Consumer Finance']
    financial_companies = set(sec_df[sec_df['broad_sector'].isin(financial_sectors) | sec_df['sub_sector'].isin(financial_sectors)]['company_id'].tolist())
    non_financial_companies = valid_companies - financial_companies
    
    # Load P&L (Header=1)
    pl_path = os.path.join(RAW_DIR, "profitandloss.xlsx")
    logger.info(f"Loading {pl_path}...")
    pl_df_raw = pd.read_excel(pl_path, header=1)
    
    pl_df, pl_failures = validate_time_series_sheet(pl_df_raw, "profitandloss", valid_companies)
    all_failures.extend(pl_failures)
    
    # Run P&L business rules (DQ-05, DQ-06, etc.)
    pl_biz_failures = validate_pl_business_rules(pl_df, non_financial_companies)
    all_failures.extend(pl_biz_failures)
    
    pl_df.to_sql("profitandloss", conn, if_exists="append", index=False)
    audit_records.append({
        'table': 'profitandloss',
        'rows_in': len(pl_df_raw),
        'rows_out': len(pl_df),
        'rejected': len(pl_df_raw) - len(pl_df),
        'timestamp': datetime.now().isoformat(),
        'runtime_s': round(time.time() - start_time, 3)
    })
    
    # Load Balance Sheet (Header=1)
    bs_path = os.path.join(RAW_DIR, "balancesheet.xlsx")
    logger.info(f"Loading {bs_path}...")
    bs_df_raw = pd.read_excel(bs_path, header=1)
    
    bs_df, bs_failures = validate_time_series_sheet(bs_df_raw, "balancesheet", valid_companies)
    all_failures.extend(bs_failures)
    
    # Run BS business rules (DQ-04, DQ-10, etc.)
    bs_biz_failures = validate_bs_business_rules(bs_df)
    all_failures.extend(bs_biz_failures)
    
    bs_df.to_sql("balancesheet", conn, if_exists="append", index=False)
    audit_records.append({
        'table': 'balancesheet',
        'rows_in': len(bs_df_raw),
        'rows_out': len(bs_df),
        'rejected': len(bs_df_raw) - len(bs_df),
        'timestamp': datetime.now().isoformat(),
        'runtime_s': round(time.time() - start_time, 3)
    })
    
    # Load Cash Flow (Header=1)
    cf_path = os.path.join(RAW_DIR, "cashflow.xlsx")
    logger.info(f"Loading {cf_path}...")
    cf_df_raw = pd.read_excel(cf_path, header=1)
    
    cf_df, cf_failures = validate_time_series_sheet(cf_df_raw, "cashflow", valid_companies)
    all_failures.extend(cf_failures)
    
    # Run CF business rules (DQ-09)
    cf_biz_failures = validate_cf_business_rules(cf_df)
    all_failures.extend(cf_biz_failures)
    
    cf_df.to_sql("cashflow", conn, if_exists="append", index=False)
    audit_records.append({
        'table': 'cashflow',
        'rows_in': len(cf_df_raw),
        'rows_out': len(cf_df),
        'rejected': len(cf_df_raw) - len(cf_df),
        'timestamp': datetime.now().isoformat(),
        'runtime_s': round(time.time() - start_time, 3)
    })
    
    # Enforce DQ-16 (Coverage Check)
    coverage_failures = validate_coverage([pl_df, bs_df, cf_df])
    all_failures.extend(coverage_failures)
    
    # Load sectors map
    sec_df.to_sql("sectors", conn, if_exists="append", index=False)
    audit_records.append({
        'table': 'sectors',
        'rows_in': len(sec_df_raw),
        'rows_out': len(sec_df),
        'rejected': len(sec_df_raw) - len(sec_df),
        'timestamp': datetime.now().isoformat(),
        'runtime_s': round(time.time() - start_time, 3)
    })
    
    # Load other core Excel sheets
    # 1. Documents (Header=1)
    doc_path = os.path.join(RAW_DIR, "documents.xlsx")
    logger.info(f"Loading {doc_path}...")
    doc_df_raw = pd.read_excel(doc_path, header=1)
    doc_df, doc_failures = validate_documents_sheet(doc_df_raw, valid_companies)
    all_failures.extend(doc_failures)
    doc_df.to_sql("documents", conn, if_exists="append", index=False)
    audit_records.append({
        'table': 'documents',
        'rows_in': len(doc_df_raw),
        'rows_out': len(doc_df),
        'rejected': len(doc_df_raw) - len(doc_df),
        'timestamp': datetime.now().isoformat(),
        'runtime_s': round(time.time() - start_time, 3)
    })
    
    # 2. Analysis (Header=1)
    an_path = os.path.join(RAW_DIR, "analysis.xlsx")
    logger.info(f"Loading {an_path}...")
    an_df_raw = pd.read_excel(an_path, header=1)
    an_df_raw['company_id'] = an_df_raw['company_id'].apply(normalize_ticker)
    an_df = an_df_raw[an_df_raw['company_id'].isin(valid_companies)].drop_duplicates(subset=['company_id']).copy()
    an_df.to_sql("analysis", conn, if_exists="append", index=False)
    audit_records.append({
        'table': 'analysis',
        'rows_in': len(an_df_raw),
        'rows_out': len(an_df),
        'rejected': len(an_df_raw) - len(an_df),
        'timestamp': datetime.now().isoformat(),
        'runtime_s': round(time.time() - start_time, 3)
    })
    
    # 3. Pros and Cons (Header=1)
    pc_path = os.path.join(RAW_DIR, "prosandcons.xlsx")
    logger.info(f"Loading {pc_path}...")
    pc_df_raw = pd.read_excel(pc_path, header=1)
    pc_df_raw['company_id'] = pc_df_raw['company_id'].apply(normalize_ticker)
    pc_df = pc_df_raw[pc_df_raw['company_id'].isin(valid_companies)].copy()
    pc_df.to_sql("prosandcons", conn, if_exists="append", index=False)
    audit_records.append({
        'table': 'prosandcons',
        'rows_in': len(pc_df_raw),
        'rows_out': len(pc_df),
        'rejected': len(pc_df_raw) - len(pc_df),
        'timestamp': datetime.now().isoformat(),
        'runtime_s': round(time.time() - start_time, 3)
    })
    
    # Load supplementary files
    # 1. Stock Prices (Header=0)
    sp_path = os.path.join(SUPPORT_DIR, "stock_prices.xlsx")
    logger.info(f"Loading {sp_path}...")
    sp_df_raw = pd.read_excel(sp_path, header=0)
    sp_df_raw['company_id'] = sp_df_raw['company_id'].apply(normalize_ticker)
    sp_df = sp_df_raw[sp_df_raw['company_id'].isin(valid_companies)].drop_duplicates(subset=['company_id', 'date']).copy()
    sp_df.to_sql("stock_prices", conn, if_exists="append", index=False)
    audit_records.append({
        'table': 'stock_prices',
        'rows_in': len(sp_df_raw),
        'rows_out': len(sp_df),
        'rejected': len(sp_df_raw) - len(sp_df),
        'timestamp': datetime.now().isoformat(),
        'runtime_s': round(time.time() - start_time, 3)
    })
    
    # 2. Market Cap (Header=0)
    mc_path = os.path.join(SUPPORT_DIR, "market_cap.xlsx")
    logger.info(f"Loading {mc_path}...")
    mc_df_raw = pd.read_excel(mc_path, header=0)
    mc_df_raw['company_id'] = mc_df_raw['company_id'].apply(normalize_ticker)
    mc_df = mc_df_raw[mc_df_raw['company_id'].isin(valid_companies)].drop_duplicates(subset=['company_id', 'year']).copy()
    mc_df.to_sql("market_cap", conn, if_exists="append", index=False)
    audit_records.append({
        'table': 'market_cap',
        'rows_in': len(mc_df_raw),
        'rows_out': len(mc_df),
        'rejected': len(mc_df_raw) - len(mc_df),
        'timestamp': datetime.now().isoformat(),
        'runtime_s': round(time.time() - start_time, 3)
    })
    
    # 3. Peer Groups (Header=0)
    pg_path = os.path.join(SUPPORT_DIR, "peer_groups.xlsx")
    logger.info(f"Loading {pg_path}...")
    pg_df_raw = pd.read_excel(pg_path, header=0)
    pg_df_raw['company_id'] = pg_df_raw['company_id'].apply(normalize_ticker)
    pg_df = pg_df_raw[pg_df_raw['company_id'].isin(valid_companies)].drop_duplicates(subset=['peer_group_name', 'company_id']).copy()
    pg_df.to_sql("peer_groups", conn, if_exists="append", index=False)
    audit_records.append({
        'table': 'peer_groups',
        'rows_in': len(pg_df_raw),
        'rows_out': len(pg_df),
        'rejected': len(pg_df_raw) - len(pg_df),
        'timestamp': datetime.now().isoformat(),
        'runtime_s': round(time.time() - start_time, 3)
    })
    
    # 4. Financial Ratios Reference (Header=0)
    fr_path = os.path.join(SUPPORT_DIR, "financial_ratios.xlsx")
    logger.info(f"Loading reference ratios {fr_path}...")
    fr_df_raw = pd.read_excel(fr_path, header=0)
    fr_df_raw['company_id'] = fr_df_raw['company_id'].apply(normalize_ticker)
    fr_df_raw['year'] = fr_df_raw['year'].apply(normalize_year)
    fr_df = fr_df_raw[(fr_df_raw['company_id'].isin(valid_companies)) & (fr_df_raw['year'] != "PARSE_ERROR")].drop_duplicates(subset=['company_id', 'year']).copy()
    # Write to financial_ratios table
    fr_df.to_sql("financial_ratios", conn, if_exists="append", index=False)
    audit_records.append({
        'table': 'financial_ratios',
        'rows_in': len(fr_df_raw),
        'rows_out': len(fr_df),
        'rejected': len(fr_df_raw) - len(fr_df),
        'timestamp': datetime.now().isoformat(),
        'runtime_s': round(time.time() - start_time, 3)
    })
    
    conn.close()
    
    # Write output audit and validation files
    write_audit_log(audit_records)
    write_failures_log(all_failures)
    
    logger.info(f"ETL Pipeline Ingestion Complete in {time.time() - start_time:.2f} seconds.")

if __name__ == "__main__":
    main()
