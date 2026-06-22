import pytest
from src.analytics.cagr import calculate_cagr

def test_cagr_normal():
    cagr_val, flag, display = calculate_cagr(100.0, 161.051, 5)
    assert cagr_val is not None
    assert abs(cagr_val - 10.0) < 0.01
    assert flag is None
    assert display == "10.0%"

def test_cagr_decline():
    cagr_val, flag, display = calculate_cagr(100.0, -50.0, 5)
    assert cagr_val is None
    assert flag == "DECLINE_TO_LOSS"
    assert display == "N/A - turned loss"

def test_cagr_turnaround():
    cagr_val, flag, display = calculate_cagr(-100.0, 200.0, 5)
    assert cagr_val is None
    assert flag == "TURNAROUND"
    assert display == "Turnaround ^"

def test_cagr_both_negative():
    cagr_val, flag, display = calculate_cagr(-100.0, -50.0, 5)
    assert cagr_val is None
    assert flag == "BOTH_NEGATIVE"
    assert display == "N/A - both loss"

def test_cagr_zero_base():
    cagr_val, flag, display = calculate_cagr(0.0, 100.0, 5)
    assert cagr_val is None
    assert flag == "ZERO_BASE"
    assert display == "N/A - base=0"

def test_cagr_insufficient():
    cagr_val, flag, display = calculate_cagr(100.0, 150.0, 2)
    assert cagr_val is None
    assert flag == "INSUFFICIENT"
    assert display == "N/A - < 3yr"
