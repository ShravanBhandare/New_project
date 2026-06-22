import pytest
import pandas as pd
from src.etl.validator import validate_bs_business_rules, validate_cf_business_rules, validate_pl_business_rules

def test_dq04_bs_balance():
    # Assets (1000) vs Liabilities (1020) -> unbalanced by > 1%
    df = pd.DataFrame([{
        'company_id': 'TCS', 'year': '2023-03',
        'equity_capital': 100, 'reserves': 900, 'borrowings': 10, 'other_liabilities': 10,
        'total_liabilities': 1020,
        'fixed_assets': 500, 'cwip': 0, 'investments': 400, 'other_asset': 100,
        'total_assets': 1000
    }])
    failures = validate_bs_business_rules(df)
    assert any(f['field'] == 'total_assets/total_liabilities' and f['severity'] == 'WARNING' for f in failures)

def test_dq06_zero_sales():
    df = pd.DataFrame([{
        'company_id': 'TCS', 'year': '2023-03',
        'sales': 0, 'expenses': 100, 'operating_profit': -100, 'opm_percentage': 0,
        'tax_percentage': 0, 'dividend_payout': 0, 'net_profit': -100, 'eps': -1.0
    }])
    failures = validate_pl_business_rules(df, non_financial_companies={'TCS'})
    assert any(f['field'] == 'sales' and f['severity'] == 'WARNING' for f in failures)

def test_dq10_negative_fixed_assets():
    df = pd.DataFrame([{
        'company_id': 'TCS', 'year': '2023-03',
        'equity_capital': 100, 'reserves': 900, 'borrowings': 0, 'other_liabilities': 0,
        'total_liabilities': 1000,
        'fixed_assets': -50.0, 'cwip': 0, 'investments': 950, 'other_asset': 100,
        'total_assets': 1000
    }])
    failures = validate_bs_business_rules(df)
    assert any(f['field'] == 'fixed_assets' and f['severity'] == 'WARNING' for f in failures)
    # Check that fixed assets were coerced to 0.0
    assert df.loc[0, 'fixed_assets'] == 0.0

def test_dq09_net_cash_flow_mismatch():
    df = pd.DataFrame([{
        'company_id': 'TCS', 'year': '2023-03',
        'operating_activity': 100.0, 'investing_activity': -50.0, 'financing_activity': -10.0,
        'net_cash_flow': 80.0 # Expected CFO + CFI + CFF = 40. Mismatch by 40 > 10.
    }])
    failures = validate_cf_business_rules(df)
    assert any(f['field'] == 'net_cash_flow' and f['severity'] == 'WARNING' for f in failures)
    # Coerced to calculated value
    assert df.loc[0, 'net_cash_flow'] == 40.0
