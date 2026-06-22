import yaml
import os
from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
from src.analytics.screener.engine import get_latest_screener_data, apply_preset_filters

router = APIRouter(prefix="/screener", tags=["Screener"])
CONFIG_PATH = "config/screener_config.yaml"

@router.get("", response_model=List[Dict[str, Any]])
def run_screener(
    preset: str = Query("quality_compounder", description="Screener preset name (e.g., quality_compounder, value_pick)")
):
    """Run a pre-configured screener preset and retrieve matching companies."""
    if not os.path.exists(CONFIG_PATH):
        raise HTTPException(status_code=500, detail="Screener configuration file not found")
        
    with open(CONFIG_PATH, 'r') as f:
        config = yaml.safe_load(f)
        
    presets = config.get('presets', {})
    if preset not in presets:
        valid_presets = list(presets.keys())
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid preset: '{preset}'. Valid options are: {valid_presets}"
        )
        
    try:
        df = get_latest_screener_data()
        filtered_df = apply_preset_filters(df, preset, config)
        
        # Round numerical values for clean response JSON
        numeric_cols = filtered_df.select_dtypes(include=['float64', 'int64']).columns
        filtered_df[numeric_cols] = filtered_df[numeric_cols].round(2)
        
        # Replace NaN/inf with None for JSON compliance
        filtered_df = filtered_df.replace([float('inf'), float('-inf')], None)
        filtered_df = filtered_df.where(filtered_df.notnull(), None)
        
        return filtered_df.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Screener execution error: {str(e)}")

@router.get("/presets", response_model=List[str])
def list_presets():
    """List all available screener presets."""
    if not os.path.exists(CONFIG_PATH):
        raise HTTPException(status_code=500, detail="Screener configuration file not found")
        
    with open(CONFIG_PATH, 'r') as f:
        config = yaml.safe_load(f)
        
    presets = config.get('presets', {})
    return list(presets.keys())
