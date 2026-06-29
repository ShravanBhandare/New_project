import pytest
from src.analytics.cashflow_kpis import (
    calculate_fcf,
    calculate_cfo_quality,
    calculate_capex_intensity,
    calculate_fcf_conversion,
    classify_capital_allocation
)

def test_calculate_fcf():
    assert calculate_fcf(150.0, 50.0) == 100.0
    assert calculate_fcf(None, 50.0) is None
    assert calculate_fcf(150.0, None) is None

def test_calculate_cfo_quality():
    assert calculate_cfo_quality(150.0, 100.0) == 1.5
    assert calculate_cfo_quality(150.0, 0.0) is None
    assert calculate_cfo_quality(150.0, -50.0) is None
    assert calculate_cfo_quality(None, 100.0) is None

def test_calculate_capex_intensity():
    assert calculate_capex_intensity(50.0, 1000.0) == 5.0
    assert calculate_capex_intensity(50.0, 0.0) is None
    assert calculate_capex_intensity(50.0, -10.0) is None
    assert calculate_capex_intensity(None, 1000.0) is None

def test_calculate_fcf_conversion():
    assert calculate_fcf_conversion(80.0, 100.0) == 80.0
    assert calculate_fcf_conversion(80.0, 0.0) is None
    assert calculate_fcf_conversion(80.0, -10.0) is None
    assert calculate_fcf_conversion(None, 100.0) is None

def test_classify_capital_allocation():
    # 1. (+, -, -) -> Healthy/Mature
    assert classify_capital_allocation(100.0, -50.0, -30.0) == 'Healthy/Mature'
    # 2. (+, -, +) -> Growth/Expansion
    assert classify_capital_allocation(100.0, -50.0, 30.0) == 'Growth/Expansion'
    # 3. (+, +, -) -> Asset Seller/Deleveraging
    assert classify_capital_allocation(100.0, 50.0, -30.0) == 'Asset Seller/Deleveraging'
    # 4. (+, +, +) -> Cash Accumulator
    assert classify_capital_allocation(100.0, 50.0, 30.0) == 'Cash Accumulator'
    # 5. (-, -, +) -> Startup/Early Stage
    assert classify_capital_allocation(-100.0, -50.0, 30.0) == 'Startup/Early Stage'
    # 6. (-, -, -) -> Severe Cash Burn
    assert classify_capital_allocation(-100.0, -50.0, -30.0) == 'Severe Cash Burn'
    # 7. (-, +, +) -> Restructuring/Survival
    assert classify_capital_allocation(-100.0, 50.0, 30.0) == 'Restructuring/Survival'
    # 8. (-, +, -) -> Asset Liquidation
    assert classify_capital_allocation(-100.0, 50.0, -30.0) == 'Asset Liquidation'
