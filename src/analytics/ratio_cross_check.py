import sqlite3
import os
import pandas as pd
import numpy as np

DB_PATH = "data/nifty100.db"
LOG_PATH = "output/ratio_edge_cases.log"

def run_cross_check():
    if not os.path.exists("output"):
        os.makedirs("output")
        
    conn = sqlite3.connect(DB_PATH)
    
    # Get latest year per company that has P&L data
    df_latest = pd.read_sql("""
        SELECT company_id, MAX(year) as latest_year 
        FROM financial_ratios 
        WHERE net_profit_margin_pct IS NOT NULL
        GROUP BY company_id
    """, conn)
    
    # Fetch ratios and company info
    query = """
        SELECT 
            c.id, c.company_name, c.roce_percentage as source_roce, c.roe_percentage as source_roe,
            s.broad_sector, s.sub_sector,
            fr.year, fr.return_on_capital_employed_pct as calc_roce, fr.return_on_equity_pct as calc_roe, fr.debt_to_equity
        FROM companies c
        LEFT JOIN sectors s ON c.id = s.company_id
        LEFT JOIN financial_ratios fr ON c.id = fr.company_id
    """
    df_all = pd.read_sql(query, conn)
    
    # Merge to get only latest year records
    df = pd.merge(df_latest, df_all, left_on=['company_id', 'latest_year'], right_on=['id', 'year'], how='inner')
    
    # Log file
    log_lines = []
    log_lines.append("=== RATIO CROSS-CHECK ANOMALIES LOG ===")
    log_lines.append(f"Analyzing {len(df)} companies for their latest full financial year.\n")
    
    # Financial companies list for D/E check
    financials = df[df['broad_sector'] == 'Financials']['company_id'].tolist()
    log_lines.append(f"Financial companies in broad_sector (Total {len(financials)}):")
    log_lines.append(f"{', '.join(financials)}\n")
    
    # 1. D/E check / suppression check
    log_lines.append("--- 1. Debt-to-Equity Validation ---")
    for idx, row in df.iterrows():
        comp = row['company_id']
        de = row['debt_to_equity']
        is_fin = row['broad_sector'] == 'Financials'
        
        # High leverage threshold: D/E > 2.0
        if de is not None and de > 2.0:
            if is_fin:
                log_lines.append(f"[INFO] {comp} ({row['broad_sector']}) has high D/E = {de:.2f} (Warning suppressed: Financial broad_sector).")
            else:
                log_lines.append(f"[WARNING] {comp} ({row['broad_sector']}) has high leverage D/E = {de:.2f}!")
        elif de is None and is_fin:
            log_lines.append(f"[INFO] {comp} ({row['broad_sector']}) D/E is suppressed/None.")
            
    log_lines.append("\n--- 2. ROCE Cross-Check (Difference > 5%) ---")
    roce_anomalies = 0
    for idx, row in df.iterrows():
        comp = row['company_id']
        c_roce = row['calc_roce']
        s_roce = row['source_roce']
        
        if c_roce is None or s_roce is None:
            continue
            
        diff = abs(c_roce - s_roce)
        if diff > 5.0:
            roce_anomalies += 1
            log_lines.append(f"[ROCE ANOMALY] Company: {comp}")
            log_lines.append(f"  Calculated ROCE: {c_roce:.2f}% (Year: {row['latest_year']})")
            log_lines.append(f"  Source ROCE: {s_roce:.2f}%")
            log_lines.append(f"  Absolute Difference: {diff:.2f}%")
            
    log_lines.append(f"Total ROCE Anomalies: {roce_anomalies}\n")
            
    log_lines.append("--- 3. ROE Cross-Check (Difference > 5%) ---")
    roe_anomalies = 0
    for idx, row in df.iterrows():
        comp = row['company_id']
        c_roe = row['calc_roe']
        s_roe = row['source_roe']
        
        if c_roe is None or s_roe is None:
            continue
            
        diff = abs(c_roe - s_roe)
        if diff > 5.0:
            roe_anomalies += 1
            log_lines.append(f"[ROE ANOMALY] Company: {comp}")
            log_lines.append(f"  Calculated ROE: {c_roe:.2f}% (Year: {row['latest_year']})")
            log_lines.append(f"  Source ROE: {s_roe:.2f}%")
            log_lines.append(f"  Absolute Difference: {diff:.2f}%")
            
    log_lines.append(f"Total ROE Anomalies: {roe_anomalies}\n")
    
    # Write log
    with open(LOG_PATH, 'w', encoding='utf-8') as f:
        f.write('\n'.join(log_lines))
        
    print(f"Cross check run completed. Logs written to {LOG_PATH}")
    conn.close()

if __name__ == "__main__":
    run_cross_check()
