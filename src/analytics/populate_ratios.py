import sqlite3
import pandas as pd
import logging
from src.analytics.ratios import calculate_roe, calculate_roce, calculate_debt_to_equity, calculate_interest_coverage

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

DB_PATH = "data/nifty100.db"

def populate_ratios():
    logger.info("Connecting to database to calculate dynamic ratios...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON;")
    
    # We want to load P&L, BS, Cash Flow, and Companies data to calculate ratios
    # Get master face_value of each company to calculate book value per share
    companies_df = pd.read_sql("SELECT id, face_value FROM companies", conn)
    face_values = dict(zip(companies_df['id'], companies_df['face_value']))
    
    # Let's join P&L, BS, and Cash Flow tables on company_id and year
    query = """
    SELECT 
        p.company_id, p.year,
        p.sales, p.expenses, p.operating_profit, p.opm_percentage, p.other_income, p.interest, p.depreciation, p.net_profit, p.eps, p.dividend_payout,
        b.equity_capital, b.reserves, b.borrowings, b.other_liabilities, b.total_liabilities, b.fixed_assets, b.cwip, b.investments, b.other_asset, b.total_assets,
        c.operating_activity, c.investing_activity, c.financing_activity, c.net_cash_flow
    FROM profitandloss p
    JOIN balancesheet b ON p.company_id = b.company_id AND p.year = b.year
    LEFT JOIN cashflow c ON p.company_id = c.company_id AND p.year = c.year
    """
    
    df = pd.read_sql(query, conn)
    logger.info(f"Loaded {len(df)} company-year records to calculate ratios.")
    
    # Prepare records for insertion
    records = []
    
    for idx, row in df.iterrows():
        comp_id = row['company_id']
        year = row['year']
        
        sales = row['sales']
        op_profit = row['operating_profit']
        net_profit = row['net_profit']
        equity_cap = row['equity_capital']
        reserves = row['reserves'] if not pd.isna(row['reserves']) else 0.0
        borrowings = row['borrowings'] if not pd.isna(row['borrowings']) else 0.0
        interest = row['interest'] if not pd.isna(row['interest']) else 0.0
        other_income = row['other_income'] if not pd.isna(row['other_income']) else 0.0
        total_assets = row['total_assets']
        
        cfo = row['operating_activity'] if not pd.isna(row['operating_activity']) else 0.0
        cfi = row['investing_activity'] if not pd.isna(row['investing_activity']) else 0.0
        
        # 1. NPM
        npm = (net_profit / sales * 100.0) if sales > 0 else None
        
        # 2. OPM
        opm = (op_profit / sales * 100.0) if (sales > 0 and op_profit is not None) else None
        
        # 3. ROE
        roe = calculate_roe(net_profit, equity_cap, reserves)
        
        # 4. Debt to Equity
        de = calculate_debt_to_equity(borrowings, equity_cap, reserves)
        
        # 5. Interest Coverage
        icr = calculate_interest_coverage(op_profit if op_profit is not None else 0.0, other_income, interest)
        
        # 6. Asset Turnover
        asset_turnover = (sales / total_assets) if total_assets > 0 else None
        
        # 7. FCF
        fcf = cfo + cfi
        
        # 8. CapEx
        capex = abs(cfi)
        
        # 9. EPS
        eps = row['eps']
        
        # 10. Book value per share: (equity + reserves) / (equity_cap / face_value)
        fv = face_values.get(comp_id, 10.0)
        fv = 10.0 if (pd.isna(fv) or fv == 0) else fv
        shares = equity_cap / fv
        bvps = ((equity_cap + reserves) / shares) if shares > 0 else None
        
        # 11. Dividend payout ratio
        div_payout = row['dividend_payout']
        
        # 12. Total Debt
        total_debt = borrowings
        
        # 13. CFO
        cfo_val = cfo
        
        records.append((
            comp_id, year, npm, opm, roe, de, icr, asset_turnover, fcf, capex, eps, bvps, div_payout, total_debt, cfo_val
        ))
        
    logger.info("Writing calculated ratios to financial_ratios table...")
    # Clear reference data that we loaded in loader.py and insert our dynamically computed values
    cursor.execute("DELETE FROM financial_ratios;")
    
    insert_query = """
    INSERT INTO financial_ratios (
        company_id, year, net_profit_margin_pct, operating_profit_margin_pct, return_on_equity_pct,
        debt_to_equity, interest_coverage, asset_turnover, free_cash_flow_cr, capex_cr,
        earnings_per_share, book_value_per_share, dividend_payout_ratio_pct, total_debt_cr, cash_from_operations_cr
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    cursor.executemany(insert_query, records)
    conn.commit()
    
    # Let's count how many rows are loaded
    cursor.execute("SELECT COUNT(*) FROM financial_ratios")
    row_count = cursor.fetchone()[0]
    logger.info(f"Populated {row_count} rows in financial_ratios table successfully.")
    
    conn.close()

if __name__ == "__main__":
    populate_ratios()
