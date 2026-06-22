from typing import Optional

def calculate_roe(net_profit: float, equity_capital: float, reserves: float) -> Optional[float]:
    """
    Return on Equity = net_profit / (equity_capital + reserves) * 100.
    None if equity + reserves <= 0.
    """
    total_equity = equity_capital + reserves
    if total_equity <= 0:
        return None
    return (net_profit / total_equity) * 100.0

def calculate_roce(ebit: float, equity_capital: float, reserves: float, borrowings: float) -> Optional[float]:
    """
    Return on Capital Employed = EBIT / (equity_capital + reserves + borrowings) * 100.
    EBIT = operating_profit - depreciation.
    None if total capital employed <= 0.
    """
    capital_employed = equity_capital + reserves + borrowings
    if capital_employed <= 0:
        return None
    return (ebit / capital_employed) * 100.0

def calculate_debt_to_equity(borrowings: float, equity_capital: float, reserves: float) -> Optional[float]:
    """
    Debt to Equity = borrowings / (equity_capital + reserves).
    None if equity_capital + reserves <= 0.
    """
    total_equity = equity_capital + reserves
    if total_equity <= 0:
        return None
    return borrowings / total_equity

def calculate_interest_coverage(operating_profit: float, other_income: float, interest: float) -> Optional[float]:
    """
    Interest Coverage = (operating_profit + other_income) / interest.
    If interest == 0, returns 999.0 (to display as 'Debt Free').
    """
    # If other_income is None, treat as 0
    other_inc = other_income if other_income is not None else 0.0
    if interest == 0:
        return 999.0
    return (operating_profit + other_inc) / interest
