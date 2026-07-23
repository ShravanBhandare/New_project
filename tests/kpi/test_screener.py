import pytest
import os
import pandas as pd
import yaml
from src.analytics.screener.engine import get_screener_data, apply_preset_filters, CONFIG_PATH

def test_screener_data_loading():
    df = get_screener_data('2024-03')
    assert not df.empty
    assert 'company_id' in df.columns
    assert 'return_on_equity_pct' in df.columns
    assert 'debt_to_equity' in df.columns
    assert 'free_cash_flow_cr' in df.columns
    assert 'sales_cagr_5yr' in df.columns

def test_apply_preset_filters():
    assert os.path.exists(CONFIG_PATH)
    with open(CONFIG_PATH, 'r') as f:
        config = yaml.safe_load(f)
        
    df = get_screener_data('2024-03')
    
    # 1. Quality Compounder
    filtered_qc = apply_preset_filters(df, 'quality_compounder', config)
    assert len(filtered_qc) > 0
    # verify conditions
    for idx, row in filtered_qc.iterrows():
        assert row['return_on_equity_pct'] > 15.0
        # debt to equity can be NaN for financials, but standard query filters it out
        # unless it is less than 1.0
        if not pd.isna(row['debt_to_equity']):
            assert row['debt_to_equity'] < 1.0
        assert row['free_cash_flow_cr'] > 0.0
        assert row['sales_cagr_5yr'] > 10.0

def test_value_pick_preset():
    with open(CONFIG_PATH, 'r') as f:
        config = yaml.safe_load(f)
    df = get_screener_data('2024-03')
    filtered_vp = apply_preset_filters(df, 'value_pick', config)
    # verify conditions for value picks using relaxed thresholds from config
    for idx, row in filtered_vp.iterrows():
        assert row['pe_ratio'] < 30.0, f"PE {row['pe_ratio']} >= 30"
        assert row['pb_ratio'] < 5.0,  f"PB {row['pb_ratio']} >= 5"
        if not pd.isna(row['debt_to_equity']):
            assert row['debt_to_equity'] < 2.0
        assert row['dividend_yield_pct'] > 0.5, f"Div yield {row['dividend_yield_pct']} <= 0.5%"
