import pytest
from src.analytics.cashflow_kpis import calculate_cfo_quality, calculate_capex_intensity, calculate_fcf_conversion, classify_capital_allocation

def test_cfo_quality():
    cfo = [120, 150, 110, 130, 140]
    pat = [100, 110, 120, 100, 110]
    # Ratios: 1.2, 1.36, 0.916, 1.3, 1.27 -> Avg: 1.21 -> High Quality
    avg, label = calculate_cfo_quality(cfo, pat)
    assert label == "High Quality Earnings"
    assert avg is not None
    assert avg > 1.0

def test_capex_intensity():
    # capex = 50, sales = 1000 -> 5.0% -> Moderate
    intensity, label = calculate_capex_intensity(50, 1000)
    assert label == "Moderate"
    assert intensity == 5.0

    # capex = 20, sales = 1000 -> 2.0% -> Asset-Light
    intensity, label = calculate_capex_intensity(20, 1000)
    assert label == "Asset-Light"
    assert intensity == 2.0

def test_fcf_conversion():
    # fcf = 70, ebitda = 100 -> 70% -> Efficient
    conversion, label = calculate_fcf_conversion(70, 100)
    assert label == "Efficient"
    assert conversion == 70.0

def test_classify_capital_allocation():
    # CFO > 0, CFI < 0, CFF < 0 -> Reinvestor / Shareholder Returns
    assert classify_capital_allocation(100, -50, -30) == "Reinvestor / Shareholder Returns"
    # CFO < 0, CFI < 0, CFF > 0 -> Distress
    assert classify_capital_allocation(-10, -5, 20) == "Distress"
