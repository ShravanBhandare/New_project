"""
src/nlp/pros_cons_generator.py
Auto-generate pros and cons for all 92 companies using 12 pro + 12 con rules.
Confidence > 60 required to include. Fallback ensures every company has at least 1 pro and 1 con.
Output: output/pros_cons_generated.csv
"""
import os
import logging
import sqlite3
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH  = "data/nifty100.db"
OUT_PATH = "output/pros_cons_generated.csv"


def load_data() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df_fr  = pd.read_sql("SELECT * FROM financial_ratios ORDER BY company_id, year", conn)
    df_c   = pd.read_sql("SELECT id as company_id, company_name FROM companies", conn)
    df_s   = pd.read_sql("SELECT company_id, broad_sector FROM sectors", conn)
    df_pl  = pd.read_sql("SELECT company_id, year, sales, operating_profit, net_profit FROM profitandloss ORDER BY company_id, year", conn)
    df_bs  = pd.read_sql("SELECT company_id, year, borrowings, total_assets FROM balancesheet ORDER BY company_id, year", conn)
    df_cf  = pd.read_sql("SELECT company_id, year, operating_activity, investing_activity, financing_activity FROM cashflow ORDER BY company_id, year", conn)
    conn.close()

    # Latest year per company for ratios
    latest_fr = df_fr.sort_values("year").groupby("company_id").last().reset_index()
    latest_pl = df_pl.sort_values("year").groupby("company_id").last().reset_index()
    latest_bs = df_bs.sort_values("year").groupby("company_id").last().reset_index()
    latest_cf = df_cf.sort_values("year").groupby("company_id").last().reset_index()

    df = df_c.merge(df_s, on="company_id", how="left")
    df = df.merge(latest_fr, on="company_id", how="left")
    df = df.merge(latest_pl[["company_id", "sales", "operating_profit", "net_profit"]], on="company_id", how="left", suffixes=("", "_pl"))
    df = df.merge(latest_bs[["company_id", "borrowings", "total_assets"]], on="company_id", how="left")
    df = df.merge(latest_cf[["company_id", "operating_activity", "financing_activity"]], on="company_id", how="left")

    # OPM
    df["opm_pct"] = np.where(
        df["sales"].notna() & (df["sales"] > 0),
        df["operating_profit"] / df["sales"] * 100, np.nan
    )
    return df, df_fr, df_pl, df_bs, df_cf


def consec_positive_fcf(company_id, df_fr, n=5) -> bool:
    sub = df_fr[df_fr["company_id"] == company_id].sort_values("year").tail(n)
    if len(sub) < n:
        return False
    return bool((sub["free_cash_flow_cr"].fillna(-1) > 0).all())


def consec_negative_fcf(company_id, df_fr, n=3) -> bool:
    sub = df_fr[df_fr["company_id"] == company_id].sort_values("year").tail(n)
    if len(sub) < n:
        return False
    return bool((sub["free_cash_flow_cr"].fillna(1) < 0).all())


def roe_high_sustained(company_id, df_fr, n=3, threshold=20) -> tuple:
    sub = df_fr[df_fr["company_id"] == company_id].sort_values("year").tail(n)
    if len(sub) < n:
        return False, 0
    vals = sub["return_on_equity_pct"].fillna(0)
    return bool((vals > threshold).all()), float(vals.mean())


def roe_improving(company_id, df_fr, n=3) -> bool:
    sub = df_fr[df_fr["company_id"] == company_id].sort_values("year").tail(n)
    if len(sub) < n:
        return False
    vals = sub["return_on_equity_pct"].fillna(0).tolist()
    return all(vals[i] < vals[i+1] for i in range(len(vals)-1))


def de_rising(company_id, df_fr, n=3) -> bool:
    sub = df_fr[df_fr["company_id"] == company_id].sort_values("year").tail(n)
    if len(sub) < n:
        return False
    vals = sub["debt_to_equity"].fillna(0).tolist()
    return all(vals[i] <= vals[i+1] for i in range(len(vals)-1)) and vals[-1] > vals[0]


def opm_declining(company_id, df_pl, n=3) -> bool:
    sub = df_pl[df_pl["company_id"] == company_id].sort_values("year").tail(n)
    if len(sub) < n:
        return False
    opm = np.where(sub["sales"] > 0, sub["operating_profit"] / sub["sales"] * 100, np.nan)
    opm = [v for v in opm if not np.isnan(v)]
    if len(opm) < n:
        return False
    return all(opm[i] > opm[i+1] for i in range(len(opm)-1))


def revenue_declining(company_id, df_pl, n=2) -> bool:
    sub = df_pl[df_pl["company_id"] == company_id].sort_values("year").tail(n)
    if len(sub) < n:
        return False
    vals = sub["sales"].fillna(0).tolist()
    return all(vals[i] >= vals[i+1] for i in range(len(vals)-1))


def eps_declining(company_id, df_fr, n=3) -> bool:
    sub = df_fr[df_fr["company_id"] == company_id].sort_values("year").tail(n)
    if len(sub) < n:
        return False
    vals = sub["earnings_per_share"].fillna(0).tolist()
    return all(vals[i] >= vals[i+1] for i in range(len(vals)-1))


def assets_growing_debt_declining(company_id, df_bs) -> bool:
    sub = df_bs[df_bs["company_id"] == company_id].sort_values("year").tail(2)
    if len(sub) < 2:
        return False
    assets_up = sub["total_assets"].iloc[-1] > sub["total_assets"].iloc[0]
    debt_down  = sub["borrowings"].iloc[-1]  < sub["borrowings"].iloc[0]
    return bool(assets_up and debt_down)


def generate_pros_cons(row, df_fr, df_pl, df_bs, df_cf) -> list:
    cid = row["company_id"]
    is_financial = str(row.get("broad_sector", "")).lower() in ("financials", "financial services")
    records = []

    roe       = float(row.get("return_on_equity_pct") or 0)
    roce      = float(row.get("roce_percentage") or 0)
    de        = float(row.get("debt_to_equity") or 0)
    fcf       = float(row.get("free_cash_flow_cr") or 0)
    div_yield = float(row.get("dividend_yield_pct") or 0)
    div_pout  = float(row.get("dividend_payout_ratio_pct") or 0)
    icr       = float(row.get("interest_coverage") or 0)
    rev_cagr  = float(row.get("sales_cagr_5yr") or 0)
    pat_cagr  = float(row.get("pat_cagr_5yr") or 0)
    eps_cagr  = float(row.get("eps_cagr_5yr") or 0)
    net_prof  = float(row.get("net_profit") or 0)
    opm       = float(row.get("opm_pct") or 0)
    total_debt = float(row.get("total_debt_cr") or 0)

    def add(rule_type, rule_id, text, confidence):
        if confidence > 60:
            records.append({"company_id": cid, "type": rule_type, "rule_id": rule_id,
                            "text": text, "confidence_pct": round(confidence, 1)})

    # ── PRO RULES ──────────────────────────────────────────
    # P1: ROE > 20% sustained 3+ years
    sustained, avg_roe = roe_high_sustained(cid, df_fr)
    if sustained:
        add("pro", "P1", "Consistently high return on equity above 20% demonstrates exceptional capital efficiency",
            min(100, avg_roe * 3))

    # P2: FCF positive 5+ years
    if consec_positive_fcf(cid, df_fr, 5):
        add("pro", "P2", "Strong free cash flow generation over 5 years signals healthy business fundamentals", 85)

    # P3: D/E = 0
    if de == 0.0:
        add("pro", "P3", "Debt-free balance sheet provides financial flexibility and eliminates interest burden", 90)

    # P4: Revenue CAGR > 15%
    if rev_cagr > 15:
        add("pro", "P4", f"Revenue growing at above 15% CAGR over 5 years reflects strong business momentum",
            min(100, rev_cagr * 4))

    # P5: OPM > 25%
    if opm > 25:
        add("pro", "P5", "Operating profit margin above 25% indicates strong pricing power and cost discipline",
            min(100, opm * 2.5))

    # P6: PAT CAGR > 20%
    if pat_cagr > 20:
        add("pro", "P6", f"Net profit compounding at above 20% over 5 years creates significant shareholder value",
            min(100, pat_cagr * 3))

    # P7: ICR > 10 or debt-free
    if icr > 10 or de == 0:
        add("pro", "P7", "Very high interest coverage ratio reflects negligible financial stress from debt servicing", 80)

    # P8: Div yield > 2% AND FCF > 0
    if div_yield > 2 and fcf > 0:
        add("pro", "P8", f"Consistent dividend yield above 2% backed by positive free cash flow", 75)

    # P9: EPS CAGR > 15%
    if eps_cagr > 15:
        add("pro", "P9", "Earnings per share growing above 15% CAGR indicates strong earnings quality and compounding",
            min(100, eps_cagr * 4))

    # P10: ROE improving 3 consecutive years
    if roe_improving(cid, df_fr, 3):
        add("pro", "P10", "Return on equity improving for 3 consecutive years shows strengthening business quality", 70)

    # P11: Revenue CAGR < PAT CAGR (operating leverage)
    if rev_cagr > 0 and pat_cagr > rev_cagr:
        add("pro", "P11", "Revenue growing slower than profits shows improving operating leverage and scale benefits", 65)

    # P12: Growing assets, declining debt
    if assets_growing_debt_declining(cid, df_bs):
        add("pro", "P12", "Growing asset base funded by internal accruals reflects self-sustaining growth", 70)

    # ── CON RULES ──────────────────────────────────────────
    # C1: D/E > 2 for non-financials
    if de > 2.0 and not is_financial:
        add("con", "C1", f"Debt-to-equity ratio of {de:.1f}x is elevated for a non-financial company and warrants monitoring",
            min(100, de * 30))

    # C2: FCF negative 3 consecutive years
    if consec_negative_fcf(cid, df_fr, 3):
        add("con", "C2", "Free cash flow negative for 3 consecutive years raises concern about cash generation quality", 85)

    # C3: OPM declining 3 consecutive years
    if opm_declining(cid, df_pl, 3):
        add("con", "C3", "Operating margins declining for 3 consecutive years suggest pricing or cost pressure", 80)

    # C4: Net profit negative latest year
    if net_prof < 0:
        add("con", "C4", "Company reported a net loss in the most recent financial year", 90)

    # C5: Revenue declining 2+ years
    if revenue_declining(cid, df_pl, 2):
        add("con", "C5", "Revenue contraction over 2 consecutive years indicates demand weakness or market share loss", 85)

    # C6: ICR < 1.5
    if 0 < icr < 1.5:
        add("con", "C6", f"Interest coverage ratio of {icr:.1f}x indicates the company is at risk of not meeting its debt obligations", 90)

    # C7: Dividend payout > 100%
    if div_pout > 100:
        add("con", "C7", "Dividend payout ratio above 100% means the company is paying dividends from reserves, which is unsustainable", 75)

    # C8: D/E rising 3 consecutive years
    if de_rising(cid, df_fr, 3):
        add("con", "C8", "Rising debt-to-equity ratio over 3 years suggests increasing financial leverage risk", 75)

    # C9: EPS declining 3 consecutive years
    if eps_declining(cid, df_fr, 3):
        add("con", "C9", "Earnings per share declining for 3 consecutive years reflects deteriorating profitability", 80)

    # C10: ROCE < 10%
    if 0 < roce < 10:
        add("con", "C10", "Return on capital employed below 10% suggests the business is not generating sufficient returns on invested capital", 70)

    # C11: Net Debt > 3x EBITDA (proxy: total_debt > 3 * operating_profit)
    ebitda_proxy = float(row.get("operating_profit") or 0)
    if total_debt > 0 and ebitda_proxy > 0 and total_debt > 3 * ebitda_proxy:
        add("con", "C11", "Net debt exceeding 3 times EBITDA is a high leverage ratio and limits financial flexibility", 85)

    # C12: Revenue CAGR < 5% over 5 years
    if rev_cagr < 5:
        add("con", "C12", "Revenue growing at below 5% over 5 years lags inflation and suggests limited business momentum",
            min(100, (5 - rev_cagr) * 15 + 50))

    return records


def ensure_coverage(records: list, companies: pd.DataFrame, df_fr: pd.DataFrame) -> list:
    """Ensure every company has at least 1 pro and 1 con, using fallback low-confidence rules."""
    df_records = pd.DataFrame(records) if records else pd.DataFrame(columns=["company_id", "type", "rule_id", "text", "confidence_pct"])
    all_ids = set(companies["company_id"].tolist())

    pros_ids = set(df_records[df_records["type"] == "pro"]["company_id"].tolist()) if not df_records.empty else set()
    cons_ids = set(df_records[df_records["type"] == "con"]["company_id"].tolist()) if not df_records.empty else set()

    missing_pros = all_ids - pros_ids
    missing_cons = all_ids - cons_ids

    fallback = []
    latest = df_fr.sort_values("year").groupby("company_id").last().reset_index()
    for cid in missing_pros:
        row = latest[latest["company_id"] == cid]
        roe = float(row["return_on_equity_pct"].values[0]) if len(row) > 0 and not pd.isna(row["return_on_equity_pct"].values[0]) else 0
        fallback.append({"company_id": cid, "type": "pro", "rule_id": "P_FALLBACK",
                         "text": f"Company demonstrates financial operations with ROE of {roe:.1f}%",
                         "confidence_pct": 61.0})

    for cid in missing_cons:
        row = latest[latest["company_id"] == cid]
        rev = float(row["sales_cagr_5yr"].values[0]) if len(row) > 0 and "sales_cagr_5yr" in row.columns and not pd.isna(row["sales_cagr_5yr"].values[0]) else 0
        fallback.append({"company_id": cid, "type": "con", "rule_id": "C_FALLBACK",
                         "text": f"Revenue CAGR of {rev:.1f}% over 5 years warrants monitoring relative to industry benchmarks",
                         "confidence_pct": 61.0})

    logger.info(f"Fallback: {len([f for f in fallback if f['type']=='pro'])} pros, "
                f"{len([f for f in fallback if f['type']=='con'])} cons added")
    return records + fallback


def run():
    os.makedirs("output", exist_ok=True)
    logger.info("Loading data for pros/cons generation...")
    df, df_fr, df_pl, df_bs, df_cf = load_data()
    companies = df[["company_id"]].drop_duplicates()

    all_records = []
    for _, row in df.iterrows():
        recs = generate_pros_cons(row, df_fr, df_pl, df_bs, df_cf)
        all_records.extend(recs)

    all_records = ensure_coverage(all_records, companies, df_fr)
    df_out = pd.DataFrame(all_records).drop_duplicates()
    df_out = df_out.sort_values(["company_id", "type", "confidence_pct"], ascending=[True, True, False])
    df_out.to_csv(OUT_PATH, index=False)

    # Stats
    n_companies_with_pros = df_out[df_out["type"] == "pro"]["company_id"].nunique()
    n_companies_with_cons = df_out[df_out["type"] == "con"]["company_id"].nunique()
    logger.info(f"Output: {len(df_out)} total entries, "
                f"{n_companies_with_pros} companies with pros, {n_companies_with_cons} with cons")
    print(f"[OK] pros_cons_generated.csv -> {len(df_out)} entries")
    print(f"     Companies with pros: {n_companies_with_pros}")
    print(f"     Companies with cons: {n_companies_with_cons}")
    return df_out


if __name__ == "__main__":
    run()
