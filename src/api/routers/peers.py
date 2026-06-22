import sqlite3
import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional

router = APIRouter(prefix="/peers", tags=["Peers"])
DB_PATH = "data/nifty100.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@router.get("", response_model=List[str])
def list_peer_groups():
    """Retrieve list of all unique peer group names."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT peer_group_name FROM peer_groups")
    groups = [row[0] for row in cursor.fetchall() if row[0]]
    conn.close()
    return groups

@router.get("/{group_name}", response_model=List[Dict[str, Any]])
def get_peer_group_details(group_name: str):
    """Retrieve peer comparison and percentile ranks for a specific peer group cohort."""
    conn = get_db_connection()
    
    # Check if group exists
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM peer_groups WHERE peer_group_name = ?", (group_name,))
    count = cursor.fetchone()[0]
    if count == 0:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Peer group '{group_name}' not found")
        
    # Query peer_percentiles for this group
    query = """
    SELECT p.company_id, c.company_name, p.metric, p.value, p.percentile_rank, p.year
    FROM peer_percentiles p
    JOIN companies c ON p.company_id = c.id
    WHERE p.peer_group = ?
    ORDER BY p.company_id, p.metric
    """
    df = pd.read_sql(query, conn, params=(group_name,))
    conn.close()
    
    if df.empty:
        raise HTTPException(status_code=404, detail="No comparison data found for this peer group")
        
    # We want to pivot or structure the records so each company is a single dict with nested metrics
    # Format: {company_id: ..., company_name: ..., metrics: {metric_name: {value: ..., percentile: ...}}}
    structured_data = {}
    for _, row in df.iterrows():
        comp_id = row['company_id']
        if comp_id not in structured_data:
            structured_data[comp_id] = {
                'company_id': comp_id,
                'company_name': row['company_name'],
                'year': row['year'],
                'metrics': {}
            }
        structured_data[comp_id]['metrics'][row['metric']] = {
            'value': round(row['value'], 2) if row['value'] is not None else None,
            'percentile_rank': round(row['percentile_rank'], 2) if row['percentile_rank'] is not None else None
        }
        
    return list(structured_data.values())
