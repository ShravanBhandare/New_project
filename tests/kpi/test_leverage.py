import pytest
from src.analytics.ratios import calculate_de, calculate_icr, calculate_asset_turnover

def test_calculate_de():
    financials = {"HDFCBANK", "ICICIBANK", "SBIN"}
    # Standard case: borrowings = 50, equity = 100, reserves = 100 -> D/E = 50 / 200 = 0.25
    assert calculate_de(50.0, 100.0, 100.0, "TCS", financials) == 0.25
    # Bank carve-out
    assert calculate_de(50.0, 100.0, 100.0, "HDFCBANK", financials) is None
    # Zero total equity case
    assert calculate_de(50.0, 0.0, 0.0, "TCS", financials) is None
    # Negative total equity case
    assert calculate_de(50.0, 50.0, -100.0, "TCS", financials) is None
    # None borrowings (treated as 0.0)
    assert calculate_de(None, 100.0, 100.0, "TCS", financials) == 0.0

def test_calculate_icr():
    # Standard case: PBT = 20, Interest = 5 -> EBIT = 25 -> ICR = 25 / 5 = 5.0
    assert calculate_icr(20.0, 5.0) == 5.0
    # Zero interest debt-free case
    assert calculate_icr(20.0, 0.0) == 999.0
    # Negative interest case
    assert calculate_icr(20.0, -5.0) == 999.0
    # None interest case
    assert calculate_icr(20.0, None) == 999.0

def test_calculate_asset_turnover():
    # Standard case: Sales = 200, Total Assets = 100 -> Turnover = 2.0
    assert calculate_asset_turnover(200.0, 100.0) == 2.0
    # Zero assets case
    assert calculate_asset_turnover(200.0, 0.0) is None
    # Negative assets case
    assert calculate_asset_turnover(200.0, -50.0) is None
    # None assets case
    assert calculate_asset_turnover(200.0, None) is None
