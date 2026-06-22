import logging
import sqlite3
import pandas as pd
from src.reports.tearsheet import generate_tearsheet_pdf
from src.reports.sector_report import generate_all_sectors
from src.reports.portfolio_report import generate_portfolio_pdf

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

DB_PATH = "data/nifty100.db"

def main():
    logger.info("Starting Nifty 100 PDF Report Generation Pipeline...")
    
    # 1. Portfolio Report
    try:
        logger.info("Generating index portfolio report...")
        generate_portfolio_pdf()
    except Exception as e:
        logger.error(f"Error generating portfolio report: {e}", exc_info=True)
        
    # 2. Sector Reports
    try:
        logger.info("Generating sector reports...")
        generate_all_sectors()
    except Exception as e:
        logger.error(f"Error generating sector reports: {e}", exc_info=True)
        
    # 3. Company Tearsheets
    try:
        logger.info("Generating constituent tearsheets...")
        conn = sqlite3.connect(DB_PATH)
        comp_ids = pd.read_sql("SELECT id FROM companies", conn)['id'].tolist()
        logger.info(f"Loaded {len(comp_ids)} tickers for tearsheets...")
        
        for i, comp_id in enumerate(comp_ids, 1):
            try:
                logger.info(f"[{i}/{len(comp_ids)}] Generating tearsheet for {comp_id}...")
                generate_tearsheet_pdf(comp_id, conn)
            except Exception as e:
                logger.error(f"Error generating tearsheet for {comp_id}: {e}", exc_info=True)
                
        conn.close()
    except Exception as e:
        logger.error(f"Error generating constituent tearsheets: {e}", exc_info=True)
        
    logger.info("Nifty 100 PDF Report Generation Pipeline finished.")

if __name__ == "__main__":
    main()
