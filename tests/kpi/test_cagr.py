import pytest
import pandas as pd
from src.analytics.cagr import calculate_cagr, find_past_value

def test_calculate_cagr_standard():
    # 3 years, 100 -> 133.1 should yield ~10.0%
    val, flag = calculate_cagr(100.0, 133.1, 3)
    assert val is not None
    assert pytest.approx(val, 0.01) == 10.0
    assert flag == 'Normal'

def test_calculate_cagr_turnaround():
    # start is negative, end is positive -> Turnaround flag, return None
    val, flag = calculate_cagr(-50.0, 50.0, 5)
    assert val is None
    assert flag == 'Turnaround'

    # start is zero, end is positive -> Turnaround flag, return None
    val, flag = calculate_cagr(0.0, 50.0, 5)
    assert val is None
    assert flag == 'Turnaround'

def test_calculate_cagr_decline_to_loss():
    # start is positive, end is negative -> Decline to Loss flag, return None
    val, flag = calculate_cagr(100.0, -10.0, 3)
    assert val is None
    assert flag == 'Decline to Loss'

    # start is positive, end is zero -> Decline to Loss flag, return None
    val, flag = calculate_cagr(100.0, 0.0, 3)
    assert val is None
    assert flag == 'Decline to Loss'

def test_calculate_cagr_retained_loss():
    # start is negative, end is negative -> Retained Loss flag, return None
    val, flag = calculate_cagr(-10.0, -20.0, 3)
    assert val is None
    assert flag == 'Retained Loss'

def test_calculate_cagr_missing():
    # start is None
    val, flag = calculate_cagr(None, 100.0, 3)
    assert val is None
    assert flag == 'Missing Data'

    # end is None
    val, flag = calculate_cagr(100.0, None, 3)
    assert val is None
    assert flag == 'Missing Data'

def test_find_past_value():
    # Create mock history for a company
    data = [
        {'year': '2024-03', 'sales': 150.0},
        {'year': '2023-03', 'sales': 120.0},
        {'year': '2021-03', 'sales': 100.0}, # Target for 3yr back from 2024-03
    ]
    df = pd.DataFrame(data)
    
    # 3 years back from 2024-03 -> 2021-03 -> sales = 100.0
    val = find_past_value(df, '2024-03', 3, 'sales')
    assert val == 100.0
    
    # 5 years back from 2024-03 -> 2019-03 -> Not found -> None
    val = find_past_value(df, '2024-03', 5, 'sales')
    assert val is None
