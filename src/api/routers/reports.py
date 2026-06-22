import os
import sqlite3
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/reports", tags=["Reports"])
DB_PATH = "data/nifty100.db"
TEARSHEETS_DIR = "reports/tearsheets"
SECTORS_DIR = "reports/sectors"
PORTFOLIO_PATH = "reports/nifty100_portfolio_report.pdf"

@router.get("/tearsheet/{ticker}")
def download_tearsheet(ticker: str):
    """Download the 2-page fundamental tearsheet PDF for a company."""
    ticker_upper = ticker.upper()
    pdf_filename = f"{ticker_upper}_tearsheet.pdf"
    pdf_path = os.path.join(TEARSHEETS_DIR, pdf_filename)
    
    # If the file does not exist, attempt to generate it on the fly
    if not os.path.exists(pdf_path):
        conn = sqlite3.connect(DB_PATH)
        # Check if company exists first
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM companies WHERE id = ?", (ticker_upper,))
        exists = cursor.fetchone()[0]
        if not exists:
            conn.close()
            raise HTTPException(status_code=404, detail=f"Company with ticker '{ticker_upper}' not found")
            
        try:
            from src.reports.tearsheet import generate_tearsheet_pdf
            generate_tearsheet_pdf(ticker_upper, conn)
        except Exception as e:
            conn.close()
            raise HTTPException(status_code=500, detail=f"Error generating tearsheet on the fly: {str(e)}")
        finally:
            conn.close()
            
    if os.path.exists(pdf_path):
        return FileResponse(
            pdf_path, 
            media_type="application/pdf", 
            filename=pdf_filename
        )
        
    raise HTTPException(status_code=404, detail="Tearsheet PDF could not be found or generated")

@router.get("/sector/{sector_name}")
def download_sector_report(sector_name: str):
    """Download the PDF report for a specific broad sector."""
    safe_name = "".join([c if c.isalnum() else "_" for c in sector_name])
    pdf_filename = f"{safe_name}_sector_report.pdf"
    pdf_path = os.path.join(SECTORS_DIR, pdf_filename)
    
    if not os.path.exists(pdf_path):
        conn = sqlite3.connect(DB_PATH)
        # Check if sector exists
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sectors WHERE broad_sector = ?", (sector_name,))
        exists = cursor.fetchone()[0]
        if not exists:
            conn.close()
            raise HTTPException(status_code=404, detail=f"Sector '{sector_name}' not found")
            
        try:
            from src.reports.sector_report import generate_sector_pdf
            generate_sector_pdf(sector_name, conn)
        except Exception as e:
            conn.close()
            raise HTTPException(status_code=500, detail=f"Error generating sector report on the fly: {str(e)}")
        finally:
            conn.close()
            
    if os.path.exists(pdf_path):
        return FileResponse(
            pdf_path, 
            media_type="application/pdf", 
            filename=pdf_filename
        )
        
    raise HTTPException(status_code=404, detail="Sector Report PDF could not be found or generated")

@router.get("/portfolio")
def download_portfolio_report():
    """Download the main Nifty 100 portfolio summary report PDF."""
    if not os.path.exists(PORTFOLIO_PATH):
        try:
            from src.reports.portfolio_report import generate_portfolio_pdf
            generate_portfolio_pdf()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error generating portfolio report on the fly: {str(e)}")
            
    if os.path.exists(PORTFOLIO_PATH):
        return FileResponse(
            PORTFOLIO_PATH, 
            media_type="application/pdf", 
            filename="nifty100_portfolio_report.pdf"
        )
        
    raise HTTPException(status_code=404, detail="Portfolio Report PDF could not be found or generated")
