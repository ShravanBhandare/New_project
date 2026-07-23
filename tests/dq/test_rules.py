"""
tests/dq/test_rules.py
14 DQ rule unit tests.
DQ-01: Company PK uniqueness
DQ-02: Duplicate (company_id, year) detection
DQ-04: Balance-sheet balance (assets ≈ liabilities, within 1%)
DQ-05: OPM cross-check (sheet vs computed)
DQ-06: Zero/negative sales for non-financials
DQ-07: Year format parsing (YYYY-MM)
DQ-08: Ticker length (2–12 chars)
DQ-09: Net cash-flow mismatch (CFO+CFI+CFF)
DQ-10: Non-negative fixed assets
DQ-11: Tax rate range (0–60%)
DQ-12: Dividend payout cap (≤ 200%)
DQ-13: Invalid URL format (no HTTP prefix)
DQ-14: EPS sign consistency with net profit
DQ-15: Strict BS balance (assets == liabilities)
DQ-16: Coverage check (≥ 5 years of data)
"""
import pytest
import pandas as pd
from src.etl.validator import (
    validate_bs_business_rules,
    validate_cf_business_rules,
    validate_pl_business_rules,
    validate_companies_sheet,
    validate_time_series_sheet,
    validate_coverage,
)


# ── helpers ──────────────────────────────────────────────────────────────────
def bs_row(**kwargs):
    base = dict(company_id="TCS", year="2023-03",
                equity_capital=100, reserves=900, borrowings=0, other_liabilities=0,
                total_liabilities=1000, fixed_assets=500, cwip=0,
                investments=400, other_asset=100, total_assets=1000)
    base.update(kwargs)
    return pd.DataFrame([base])


def pl_row(**kwargs):
    base = dict(company_id="TCS", year="2023-03",
                sales=1000, expenses=700, operating_profit=300, opm_percentage=30.0,
                tax_percentage=25.0, dividend_payout=30.0, net_profit=200, eps=2.0)
    base.update(kwargs)
    return pd.DataFrame([base])


def cf_row(**kwargs):
    base = dict(company_id="TCS", year="2023-03",
                operating_activity=100.0, investing_activity=-50.0,
                financing_activity=-10.0, net_cash_flow=40.0)
    base.update(kwargs)
    return pd.DataFrame([base])


# ── DQ-01: Company PK uniqueness ─────────────────────────────────────────────
def test_dq01_duplicate_ticker():
    df = pd.DataFrame([{"id": "TCS", "company_name": "TCS"},
                       {"id": "TCS", "company_name": "TCS Duplicate"}])
    _, failures = validate_companies_sheet(df)
    assert any(f["field"] == "id" for f in failures), "Expected DQ-01 failure for duplicate ticker"


# ── DQ-02: Duplicate (company_id, year) in time-series ───────────────────────
def test_dq02_duplicate_year():
    df = pd.DataFrame([
        {"company_id": "TCS", "year": "2023-03"},
        {"company_id": "TCS", "year": "2023-03"},
    ])
    _, failures = validate_time_series_sheet(df, "P&L", {"TCS"})
    assert any("DQ-02" in f["issue"] for f in failures), "Expected DQ-02 failure for duplicate (cid, year)"


# ── DQ-04: Balance-sheet unbalanced ──────────────────────────────────────────
def test_dq04_bs_balance():
    df = bs_row(total_liabilities=1020)   # 1020 vs assets 1000 → >1% gap
    failures = validate_bs_business_rules(df)
    assert any(f["field"] == "total_assets/total_liabilities" and f["severity"] == "WARNING"
               for f in failures)


# ── DQ-05: OPM cross-check ───────────────────────────────────────────────────
def test_dq05_opm_mismatch():
    # Sales=1000, op_profit=300 → calc OPM=30; sheet says 10 → >1% diff
    df = pl_row(opm_percentage=10.0)
    failures = validate_pl_business_rules(df, non_financial_companies={"TCS"})
    assert any(f["field"] == "opm_percentage" for f in failures)


# ── DQ-06: Zero sales for non-financial ──────────────────────────────────────
def test_dq06_zero_sales():
    df = pl_row(sales=0, operating_profit=-100, opm_percentage=0, net_profit=-100, eps=-1.0)
    failures = validate_pl_business_rules(df, non_financial_companies={"TCS"})
    assert any(f["field"] == "sales" and f["severity"] == "WARNING" for f in failures)


# ── DQ-07: Bad year format ───────────────────────────────────────────────────
def test_dq07_bad_year_format():
    df = pd.DataFrame([{"company_id": "TCS", "year": "INVALID-YR"}])
    _, failures = validate_time_series_sheet(df, "P&L", {"TCS"})
    assert any(f["field"] == "year" for f in failures), "Expected DQ-07 failure for bad year"


# ── DQ-08: Ticker too short ───────────────────────────────────────────────────
def test_dq08_short_ticker():
    df = pd.DataFrame([{"id": "T", "company_name": "Short"}])
    _, failures = validate_companies_sheet(df)
    assert any(f["field"] == "id" for f in failures), "Expected DQ-08 failure for short ticker"


# ── DQ-09: Net cash-flow mismatch ────────────────────────────────────────────
def test_dq09_net_cash_flow_mismatch():
    df = cf_row(net_cash_flow=80.0)   # calc = 40, sheet = 80 → diff > 10
    failures = validate_cf_business_rules(df)
    assert any(f["field"] == "net_cash_flow" and f["severity"] == "WARNING" for f in failures)
    assert df.loc[0, "net_cash_flow"] == 40.0  # coerced to calculated


# ── DQ-10: Negative fixed assets ─────────────────────────────────────────────
def test_dq10_negative_fixed_assets():
    df = bs_row(fixed_assets=-50.0, total_assets=1000)
    failures = validate_bs_business_rules(df)
    assert any(f["field"] == "fixed_assets" and f["severity"] == "WARNING" for f in failures)
    assert df.loc[0, "fixed_assets"] == 0.0   # coerced to 0


# ── DQ-11: Tax rate out of range ─────────────────────────────────────────────
def test_dq11_tax_rate_out_of_range():
    df = pl_row(tax_percentage=75.0)  # >60 → warning
    failures = validate_pl_business_rules(df, non_financial_companies={"TCS"})
    assert any(f["field"] == "tax_percentage" for f in failures)


# ── DQ-12: Dividend payout > 200% ────────────────────────────────────────────
def test_dq12_high_dividend_payout():
    df = pl_row(dividend_payout=250.0)
    failures = validate_pl_business_rules(df, non_financial_companies={"TCS"})
    assert any(f["field"] == "dividend_payout" for f in failures)


# ── DQ-13: Invalid URL format ─────────────────────────────────────────────────
def test_dq13_invalid_url():
    """Validate that a non-HTTP URL is flagged as DQ-13 in documents validation."""
    from src.etl.validator import validate_documents_sheet
    df = pd.DataFrame([{
        "company_id": "TCS", "Year": 2023,
        "Annual_Report": "not-a-url"   # not http → should flag
    }])
    _, failures = validate_documents_sheet(df, valid_companies={"TCS"})
    assert any("DQ-13" in str(f.get("issue", "")) for f in failures)


# ── DQ-14: EPS sign inconsistency ────────────────────────────────────────────
def test_dq14_eps_sign():
    df = pl_row(net_profit=200, eps=-1.0)   # positive profit but negative EPS
    failures = validate_pl_business_rules(df, non_financial_companies={"TCS"})
    assert any(f["field"] == "eps" for f in failures)


# ── DQ-15: Strict BS balance ─────────────────────────────────────────────────
def test_dq15_strict_bs_balance():
    df = bs_row(total_liabilities=1001, total_assets=1000)
    failures = validate_bs_business_rules(df)
    # DQ-15 logs as INFO; confirm the rule fires
    assert any("DQ-15" in str(f.get("issue", "")) for f in failures)


# ── DQ-16: Coverage check (<5 years) ─────────────────────────────────────────
def test_dq16_insufficient_coverage():
    dfs = [
        pd.DataFrame([
            {"company_id": "TCS", "year": "2023-03"},
            {"company_id": "TCS", "year": "2022-03"},
            {"company_id": "TCS", "year": "2021-03"},
        ])
    ]
    failures = validate_coverage(dfs)
    assert any(f["company_id"] == "TCS" and "DQ-16" in f["issue"] for f in failures)
