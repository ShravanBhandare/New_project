import sqlite3
import time
from fastapi import APIRouter
from typing import Dict, Any

router = APIRouter(prefix="/health", tags=["System Health"])
DB_PATH = "data/nifty100.db"
START_TIME = time.time()

@router.get("", response_model=Dict[str, Any])
def health_check():
    """Verify server status, database connections, and return record counts."""
    db_status = "unhealthy"
    counts = {}
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check tables and get record counts
        cursor.execute("SELECT COUNT(*) FROM companies")
        counts['companies'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM financial_ratios")
        counts['financial_ratios'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM profitandloss")
        counts['profit_and_loss_records'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM balancesheet")
        counts['balance_sheet_records'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM cashflow")
        counts['cash_flow_records'] = cursor.fetchone()[0]
        
        conn.close()
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
        
    uptime = time.time() - START_TIME
    
    return {
        "status": "up",
        "uptime_seconds": round(uptime, 2),
        "database": {
            "status": db_status,
            "metrics": counts
        }
    }
