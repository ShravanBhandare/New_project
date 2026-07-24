"""
src/reports/generate_all_tearsheets.py

Batch tearsheet generator for all 92 companies in the Nifty 100 universe.
- Saves PDFs to reports/tearsheets/<company_id>_tearsheet.pdf
- Skips companies with < 3 years of historical financial data
- Logs skipped companies to output/skipped_tearsheets.csv
- Validates that all generated PDFs have exactly 2 pages with 0 overflow
"""

import os
import re
import sqlite3
import logging
import pandas as pd

from src.reports.tearsheet import generate_tearsheet

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "nifty100.db")
TEARSHEET_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "reports", "tearsheets")
SKIPPED_CSV = os.path.join(os.path.dirname(__file__), "..", "..", "output", "skipped_tearsheets.csv")


def run_batch_tearsheets(db_path: str = DB_PATH):
    """
    Run batch tearsheet generation for all 92 companies.
    """
    os.makedirs(TEARSHEET_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(SKIPPED_CSV), exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    df_comp = pd.read_sql("SELECT id, company_name FROM companies ORDER BY id", conn)
    
    skipped_records = []
    generated_count = 0
    overflow_count = 0
    
    print(f"=== STARTING BATCH TEARSHEET GENERATION ({len(df_comp)} COMPANIES) ===")
    
    for _, row in df_comp.iterrows():
        cid = row['id']
        name = row['company_name']
        
        # Check annual statement count
        cnt = pd.read_sql(
            "SELECT COUNT(*) as c FROM profitandloss WHERE company_id = ? AND year LIKE '%-03'",
            conn, params=(cid,)
        ).iloc[0]['c']
        
        if cnt < 3:
            logger.info(f"Skipping {cid} ({name}): Only {cnt} year(s) of annual data available (< 3 years constraint).")
            skipped_records.append({
                'company_id': cid,
                'company_name': name,
                'year_count': cnt,
                'reason': 'Fewer than 3 years of financial statement data'
            })
            continue
            
        out_pdf = os.path.join(TEARSHEET_DIR, f"{cid}_tearsheet.pdf")
        try:
            generate_tearsheet(cid, out_pdf)
            
            # Verify page count
            with open(out_pdf, 'rb') as f:
                content = f.read()
            pages = len(re.findall(rb'/Type\s*/Page[^s]', content))
            
            if pages == 2:
                generated_count += 1
            else:
                overflow_count += 1
                logger.error(f"[OVERFLOW] {cid} generated {pages} pages instead of 2!")
        except Exception as e:
            logger.error(f"Error generating tearsheet for {cid}: {e}")
            skipped_records.append({
                'company_id': cid,
                'company_name': name,
                'year_count': cnt,
                'reason': f"Generation Error: {e}"
            })

    conn.close()

    # Save skipped csv
    df_skipped = pd.DataFrame(skipped_records)
    df_skipped.to_csv(SKIPPED_CSV, index=False)
    print(f"\nSaved skipped log to: {SKIPPED_CSV} ({len(skipped_records)} records)")

    # Final Directory Count Verification
    pdf_files = [f for f in os.listdir(TEARSHEET_DIR) if f.endswith('_tearsheet.pdf')]
    total_pdfs = len(pdf_files)
    
    print("\n=== TEARSHEET BATCH GENERATION SUMMARY ===")
    print(f"Total Companies in Universe: {len(df_comp)}")
    print(f"Skipped Companies (<3 yrs):  {len(skipped_records)}")
    print(f"Successfully Generated:      {generated_count}")
    print(f"Page Count Overflows:        {overflow_count}")
    print(f"Total PDFs in {TEARSHEET_DIR}: {total_pdfs}")
    
    expected_pdfs = len(df_comp) - len(skipped_records)
    assert total_pdfs == expected_pdfs, f"PDF count mismatch! Found {total_pdfs}, expected {expected_pdfs}"
    assert overflow_count == 0, f"Found {overflow_count} page overflow errors!"
    print("[VERIFIED] All generated tearsheets strictly meet the 2-page constraint!")


if __name__ == "__main__":
    run_batch_tearsheets()
