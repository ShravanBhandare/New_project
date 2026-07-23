"""
src/nlp/parser.py
Parse analysis.xlsx text fields using regex.
Extracts (period_years, value_pct) from text like "10 Years: 21%"
Outputs: output/analysis_parsed.csv, output/parse_failures.csv
"""
import re
import os
import logging
import pandas as pd
import numpy as np
import sqlite3

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ANALYSIS_PATH = "data/raw/analysis.xlsx"
DB_PATH       = "data/nifty100.db"
PARSED_CSV    = "output/analysis_parsed.csv"
FAILURES_CSV  = "output/parse_failures.csv"

# Target fields and their metric_type labels
FIELDS = {
    "compounded_sales_growth":   "compounded_sales_growth",
    "compounded_profit_growth":  "compounded_profit_growth",
    "stock_price_cagr":          "stock_price_cagr",
    "roe":                       "roe",
}

# Regex: extract period (as years int) and value (float %)
# Handles: "10 Years: 21%", "5 Years: 10%", "TTM: 43%", "Last Year: 12%", "3 Years: 17%"
PATTERNS = [
    # "10 Years: 21%" or "5 Years:  21%"
    (re.compile(r'(\d+)\s*Years?\s*:?\s*([\d.]+)\s*%', re.IGNORECASE), "years"),
    # "TTM: 43%" or "TTM 43%"
    (re.compile(r'TTM\s*:?\s*([\d.]+)\s*%', re.IGNORECASE),            "ttm"),
    # "Last Year: 12%" or "1 Year: 12%"
    (re.compile(r'(?:Last\s*Year|1\s*Year)\s*:?\s*([\d.]+)\s*%', re.IGNORECASE), "last_year"),
]


def parse_text_entry(text: str) -> list[tuple]:
    """Return list of (period_years, value_pct) tuples parsed from a text cell."""
    if not isinstance(text, str):
        return []
    results = []
    # Try multi-year pattern
    for match in PATTERNS[0][0].finditer(text):
        period = int(match.group(1))
        value  = float(match.group(2))
        results.append((period, value))
    # Try TTM
    for match in PATTERNS[1][0].finditer(text):
        results.append((1, float(match.group(1))))
    # Try Last Year / 1 Year (only if not already captured by multi-year)
    for match in PATTERNS[2][0].finditer(text):
        results.append((1, float(match.group(1))))
    return results


def load_analysis() -> pd.DataFrame:
    df = pd.read_excel(ANALYSIS_PATH, header=1)
    return df


def run():
    os.makedirs("output", exist_ok=True)
    logger.info("Loading analysis.xlsx ...")
    df = load_analysis()
    logger.info(f"Loaded {len(df)} rows, columns: {list(df.columns)}")

    parsed_rows  = []
    failure_rows = []

    for _, row in df.iterrows():
        company_id = str(row.get("company_id", "")).strip()
        if not company_id:
            continue

        for field_col, metric_type in FIELDS.items():
            text = str(row.get(field_col, "")).strip()
            if not text or text in ("nan", "None", ""):
                failure_rows.append({
                    "company_id": company_id, "field": field_col,
                    "raw_text": text, "reason": "empty_field"
                })
                continue

            entries = parse_text_entry(text)
            if not entries:
                failure_rows.append({
                    "company_id": company_id, "field": field_col,
                    "raw_text": text, "reason": "no_regex_match"
                })
            else:
                for period, value in entries:
                    parsed_rows.append({
                        "company_id":   company_id,
                        "metric_type":  metric_type,
                        "period_years": period,
                        "value_pct":    value,
                    })

    df_parsed = pd.DataFrame(parsed_rows)
    df_parsed.to_csv(PARSED_CSV, index=False)
    logger.info(f"Parsed {len(df_parsed)} entries -> {PARSED_CSV}")

    # Cross-validate compounded_sales_growth (5yr) vs sales_cagr_5yr from financial_ratios
    conn = sqlite3.connect(DB_PATH)
    df_fr = pd.read_sql(
        "SELECT company_id, sales_cagr_5yr FROM financial_ratios WHERE year = '2024-03'", conn
    )
    conn.close()

    divergences = []
    if not df_parsed.empty:
        sales_5yr = df_parsed[
            (df_parsed["metric_type"] == "compounded_sales_growth") &
            (df_parsed["period_years"] == 5)
        ][["company_id", "value_pct"]].rename(columns={"value_pct": "parsed_cagr"})

        merged = sales_5yr.merge(df_fr, on="company_id", how="inner")
        merged["diff"] = abs(merged["parsed_cagr"] - merged["sales_cagr_5yr"].fillna(0))
        flagged = merged[merged["diff"] > 5.0]
        for _, r in flagged.iterrows():
            divergences.append({
                "company_id": r["company_id"], "field": "compounded_sales_growth",
                "raw_text": f"parsed={r['parsed_cagr']:.1f}% vs engine={r['sales_cagr_5yr']:.1f}%",
                "reason": "CAGR_DIVERGENCE"
            })
        logger.info(f"Cross-validation: {len(flagged)} companies with CAGR divergence > 5%")

    # Combine failures
    all_failures = pd.DataFrame(failure_rows + divergences)
    all_failures.to_csv(FAILURES_CSV, index=False)
    logger.info(f"Failures/divergences: {len(all_failures)} -> {FAILURES_CSV}")

    print(f"[OK] analysis_parsed.csv -> {len(df_parsed)} rows")
    print(f"[OK] parse_failures.csv -> {len(all_failures)} rows")
    return df_parsed


if __name__ == "__main__":
    run()
