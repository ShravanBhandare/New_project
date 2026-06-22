import re

def normalize_ticker(ticker: str) -> str:
    """Strip whitespace and convert to uppercase."""
    if not isinstance(ticker, str):
        ticker = str(ticker)
    return ticker.strip().upper()

def normalize_year(year_val) -> str:
    """
    Normalise different financial year representations to YYYY-MM.
    Expected mappings:
    - Mar-23, Mar 23, March-2023, FY23, 2023 -> 2023-03
    - Dec-22 -> 2022-12
    - Jun-23 -> 2023-06
    - 2023-03 -> 2023-03
    - Unparseable -> PARSE_ERROR
    """
    if year_val is None or (isinstance(year_val, float) and year_val != year_val):
        return "PARSE_ERROR"
        
    s = str(year_val).strip()
    
    # Check if already in YYYY-MM format
    if re.match(r'^\d{4}-\d{2}$', s):
        return s
        
    # Match integer years like 2023
    if re.match(r'^\d{4}$', s):
        return f"{s}-03"
        
    # Match FYxx or FYxxxx (e.g. FY23, FY2023)
    fy_match = re.match(r'^FY\s*(\d{2,4})$', s, re.IGNORECASE)
    if fy_match:
        yr = fy_match.group(1)
        if len(yr) == 2:
            return f"20{yr}-03"
        elif len(yr) == 4:
            return f"{yr}-03"
            
    # Match patterns like Mar-23, Mar 23, Dec-22, Jun-23, March-2023, March 2023
    months_map = {
        'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04', 'may': '05', 'jun': '06',
        'jul': '07', 'aug': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12',
        'january': '01', 'february': '02', 'march': '03', 'april': '04', 'june': '06',
        'july': '07', 'august': '08', 'september': '09', 'october': '10', 'november': '11', 'december': '12'
    }
    
    # Split by hyphen or space or slash
    parts = re.split(r'[-/\s]+', s)
    if len(parts) == 2:
        p1, p2 = parts[0].lower(), parts[1]
        # Check if first part is month and second is year
        if p1 in months_map:
            mm = months_map[p1]
            if len(p2) == 2:
                # assume 20xx
                return f"20{p2}-{mm}"
            elif len(p2) == 4:
                return f"{p2}-{mm}"
        # Check if second part is month and first is year
        p2_lower = p2.lower()
        if p2_lower in months_map:
            mm = months_map[p2_lower]
            if len(p1) == 2:
                return f"20{p1}-{mm}"
            elif len(p1) == 4:
                return f"{p1}-{mm}"

    return "PARSE_ERROR"
