import pytest
from src.analytics.ratios import calculate_npm, calculate_opm, calculate_roe, calculate_roce

def test_calculate_npm():
    # Standard case
    assert calculate_npm(15.0, 100.0) == 15.0
    # Zero sales case
    assert calculate_npm(15.0, 0.0) is None
    # Negative sales case
    assert calculate_npm(15.0, -10.0) is None
    # None sales case
    assert calculate_npm(15.0, None) is None
    # None net profit case
    assert calculate_npm(None, 100.0) is None

def test_calculate_opm():
    # Standard case
    assert calculate_opm(25.0, 100.0) == 25.0
    # Zero sales case
    assert calculate_opm(25.0, 0.0) is None
    # Negative sales case
    assert calculate_opm(25.0, -5.0) is None
    # None sales case
    assert calculate_opm(25.0, None) is None

def test_calculate_roe():
    # Standard case: Net profit = 15, Equity = 50, Reserves = 50 -> ROE = (15 / 100) * 100 = 15%
    assert calculate_roe(15.0, 50.0, 50.0) == 15.0
    # Zero equity case
    assert calculate_roe(15.0, 0.0, 0.0) is None
    # Negative equity case
    assert calculate_roe(15.0, 10.0, -20.0) is None
    # None equity case (treated as 0.0, so if reserves is 100.0 it works)
    assert calculate_roe(15.0, None, 100.0) == 15.0
    # None profit case
    assert calculate_roe(None, 50.0, 50.0) is None

def test_calculate_roce():
    # Standard case: PBT = 20, Interest = 5, Equity = 50, Reserves = 30, Borrowings = 20
    # EBIT = 25, Capital Employed = 100 -> ROCE = (25 / 100) * 100 = 25%
    assert calculate_roce(20.0, 5.0, 50.0, 30.0, 20.0) == 25.0
    # Zero capital employed case
    assert calculate_roce(20.0, 5.0, 0.0, 0.0, 0.0) is None
    # Negative capital employed case
    assert calculate_roce(20.0, 5.0, 10.0, -30.0, 10.0) is None
