from typing import Tuple, Optional

def calculate_cagr(start_val: float, end_val: float, n: int) -> Tuple[Optional[float], Optional[str], str]:
    """
    Calculate CAGR with custom edge cases handling:
    - Base > 0, End > 0 -> Normal calculation
    - Base > 0, End < 0 -> Decline to loss (None, 'DECLINE_TO_LOSS', 'N/A - turned loss')
    - Base < 0, End > 0 -> Turnaround (None, 'TURNAROUND', 'Turnaround ^')
    - Base < 0, End < 0 -> Both negative (None, 'BOTH_NEGATIVE', 'N/A - both loss')
    - Base == 0 -> Zero base (None, 'ZERO_BASE', 'N/A - base=0')
    - n < 3 -> Insufficient history (None, 'INSUFFICIENT', 'N/A - < 3yr')
    """
    if n < 3:
        return None, "INSUFFICIENT", "N/A - < 3yr"
        
    if start_val == 0:
        return None, "ZERO_BASE", "N/A - base=0"
        
    if start_val > 0 and end_val < 0:
        return None, "DECLINE_TO_LOSS", "N/A - turned loss"
        
    if start_val < 0 and end_val > 0:
        return None, "TURNAROUND", "Turnaround ^"
        
    if start_val < 0 and end_val < 0:
        return None, "BOTH_NEGATIVE", "N/A - both loss"
        
    try:
        cagr_val = ((end_val / start_val) ** (1.0 / n) - 1.0) * 100.0
        return cagr_val, None, f"{cagr_val:.1f}%"
    except Exception as e:
        return None, "ERROR", f"Error: {e}"
