from typing import Tuple, Optional, List

def calculate_cfo_quality(cfo_history: List[float], pat_history: List[float]) -> Tuple[Optional[float], str]:
    """
    CFO Quality Score = Average CFO / PAT over 5 years.
    Returns: (average_ratio, label)
    Labels:
    - avg_ratio > 1.0 -> 'High Quality Earnings'
    - avg_ratio < 0.5 -> 'Accrual Risk'
    - otherwise -> 'Normal'
    """
    if not cfo_history or not pat_history or len(cfo_history) != len(pat_history):
        return None, "Normal"
        
    ratios = []
    for cfo, pat in zip(cfo_history[-5:], pat_history[-5:]):
        if pat == 0:
            continue
        ratios.append(cfo / pat)
        
    if not ratios:
        return None, "Normal"
        
    avg_ratio = sum(ratios) / len(ratios)
    if avg_ratio > 1.0:
        return avg_ratio, "High Quality Earnings"
    elif avg_ratio < 0.5:
        return avg_ratio, "Accrual Risk"
    else:
        return avg_ratio, "Normal"

def calculate_capex_intensity(capex: float, sales: float) -> Tuple[Optional[float], str]:
    """
    CapEx Intensity = CapEx / Sales * 100.
    None if sales == 0.
    Labels:
    - intensity < 3% -> 'Asset-Light'
    - intensity > 8% -> 'Capital-Intensive'
    - otherwise -> 'Moderate'
    """
    if sales == 0:
        return None, "Moderate"
    intensity = (abs(capex) / sales) * 100.0
    if intensity < 3.0:
        return intensity, "Asset-Light"
    elif intensity > 8.0:
        return intensity, "Capital-Intensive"
    else:
        return intensity, "Moderate"

def calculate_fcf_conversion(fcf: float, ebitda: float) -> Tuple[Optional[float], str]:
    """
    FCF Conversion = FCF / EBITDA * 100.
    None if EBITDA == 0.
    Labels:
    - conversion > 60% -> 'Efficient'
    - conversion < 30% -> 'CapEx Heavy'
    - otherwise -> 'Moderate'
    """
    if ebitda == 0:
        return None, "Moderate"
    conversion = (fcf / ebitda) * 100.0
    if conversion > 60.0:
        return conversion, "Efficient"
    elif conversion < 30.0:
        return conversion, "CapEx Heavy"
    else:
        return conversion, "Moderate"

def classify_capital_allocation(cfo: float, cfi: float, cff: float) -> str:
    """
    Classify 8 CFO/CFI/CFF sign patterns into descriptive labels:
    - + - - (CFO > 0, CFI < 0, CFF < 0) -> 'Reinvestor' or 'Shareholder Returns'
    - - ? + (CFO < 0, CFF > 0) -> 'Distress'
    ...
    """
    cfo_sign = "+" if cfo >= 0 else "-"
    cfi_sign = "+" if cfi >= 0 else "-"
    cff_sign = "+" if cff >= 0 else "-"
    
    pattern = f"{cfo_sign} {cfi_sign} {cff_sign}"
    
    pattern_map = {
        "+ - -": "Reinvestor / Shareholder Returns",
        "+ - +": "Expansionary Finance / Growth",
        "+ + -": "Shareholder Payback / Cash Divestment",
        "+ + +": "High Cash Accumulation",
        "- - +": "Distress",
        "- + +": "Asset Divestment / Survival",
        "- + -": "Capital Reduction / Shrinkage",
        "- - -": "Severe Cash Burn"
    }
    
    return pattern_map.get(pattern, "Undefined")
