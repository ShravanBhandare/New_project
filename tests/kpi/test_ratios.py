import pytest
from src.analytics.ratios import calculate_roe, calculate_roce, calculate_debt_to_equity, calculate_interest_coverage

def test_roe_positive():
    # net_profit = 100, equity_capital = 100, reserves = 400
    # ROE = 100 / (100 + 400) * 100 = 20.0%
    assert calculate_roe(100.0, 100.0, 400.0) == 20.0

def test_roe_neg_equity():
    # reserves + equity_capital <= 0 -> returns None
    assert calculate_roe(100.0, 100.0, -150.0) is None

def test_de_debtfree():
    # borrowings = 0 -> D/E = 0.0
    assert calculate_debt_to_equity(0.0, 100.0, 400.0) == 0.0

def test_de_normal():
    # borrowings = 250, equity = 100, reserves = 400
    # D/E = 250 / 500 = 0.5
    assert calculate_debt_to_equity(250.0, 100.0, 400.0) == 0.5

def test_icr_debtfree():
    # interest = 0 -> returns 999.0 (to represent 'Debt Free' or flag)
    assert calculate_interest_coverage(100.0, 10.0, 0.0) == 999.0

def test_icr_normal():
    # op_profit = 100, other_income = 20, interest = 30
    # ICR = (100 + 20) / 30 = 4.0
    assert calculate_interest_coverage(100.0, 20.0, 30.0) == 4.0
