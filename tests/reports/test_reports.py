import os
import sqlite3
import pytest
from src.reports.tearsheet import generate_tearsheet_pdf
from src.reports.sector_report import generate_sector_pdf
from src.reports.portfolio_report import generate_portfolio_pdf

DB_PATH = "data/nifty100.db"

def test_generate_single_tearsheet():
    conn = sqlite3.connect(DB_PATH)
    ticker = "HDFCBANK"
    pdf_path = f"reports/tearsheets/{ticker}_tearsheet.pdf"
    
    # Remove if exists to verify generation
    if os.path.exists(pdf_path):
        os.remove(pdf_path)
        
    generate_tearsheet_pdf(ticker, conn)
    conn.close()
    
    assert os.path.exists(pdf_path)
    assert os.path.getsize(pdf_path) > 0

def test_generate_single_sector_report():
    conn = sqlite3.connect(DB_PATH)
    sector = "Financials"
    pdf_path = f"reports/sectors/{sector}_sector_report.pdf"
    
    if os.path.exists(pdf_path):
        os.remove(pdf_path)
        
    generate_sector_pdf(sector, conn)
    conn.close()
    
    assert os.path.exists(pdf_path)
    assert os.path.getsize(pdf_path) > 0

def test_generate_portfolio_report():
    pdf_path = "reports/nifty100_portfolio_report.pdf"
    
    if os.path.exists(pdf_path):
        os.remove(pdf_path)
        
    generate_portfolio_pdf()
    
    assert os.path.exists(pdf_path)
    assert os.path.getsize(pdf_path) > 0
