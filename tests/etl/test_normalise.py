import pytest
import math
from src.etl.normaliser import normalize_ticker, normalize_year

@pytest.mark.parametrize("input_val, expected", [
    ("TCS", "TCS"),
    ("  TCS", "TCS"),
    ("TCS  ", "TCS"),
    ("  TCS  ", "TCS"),
    ("tcs", "TCS"),
    ("Tcs", "TCS"),
    ("BAJAJ-AUTO", "BAJAJ-AUTO"),
    ("M&M", "M&M"),
    ("DRREDDY.NS", "DRREDDY.NS"),
    ("NIFTY100", "NIFTY100"),
    (123, "123"),
    (12.3, "12.3"),
    ("RELIANCE_INDUSTRIES", "RELIANCE_INDUSTRIES"),
    ("\tTCS\t", "TCS"),
    ("\nTCS\n", "TCS"),
])
def test_normalize_ticker_cases(input_val, expected):
    assert normalize_ticker(input_val) == expected

@pytest.mark.parametrize("input_val, expected", [
    ("2023-03", "2023-03"),
    ("2022-12", "2022-12"),
    ("2023-06", "2023-06"),
    ("2024-09", "2024-09"),
    ("Mar-23", "2023-03"),
    ("Dec-22", "2022-12"),
    ("Jun-23", "2023-06"),
    ("Sep-24", "2024-09"),
    ("March-2023", "2023-03"),
    ("December 2022", "2022-12"),
    ("June/2023", "2023-06"),
    ("FY24", "2024-03"),
    ("FY 23", "2023-03"),
    ("FY2025", "2025-03"),
    (2023, "2023-03"),
    (2024, "2024-03"),
    ("2023", "2023-03"),
    ("23-Mar", "2023-03"),
    ("2022/Dec", "2022-12"),
    ("xyz", "PARSE_ERROR"),
    (12.34, "PARSE_ERROR"),
    (None, "PARSE_ERROR"),
    (float('nan'), "PARSE_ERROR"),
])
def test_normalize_year_cases(input_val, expected):
    if isinstance(input_val, float) and math.isnan(input_val):
        # special check for nan
        assert normalize_year(input_val) == "PARSE_ERROR"
    else:
        assert normalize_year(input_val) == expected
