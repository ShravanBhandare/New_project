"""
pages/03_screener.py — Enhanced Investment Screener
10 metric sliders, 6 preset buttons, live results table, CSV download
"""
import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import yaml
import io
import os

st.set_page_config(page_title="Screener | Nifty 100", layout="wide")

DB_PATH = "data/nifty100.db"
CONFIG_PATH = "config/screener_config.yaml"

# ── Preset definitions ────────────────────────────────────────
PRESETS = {
    "Quality Compounder": {"roe_min": 15.0, "de_max": 1.0, "fcf_min": 0.0, "rev_cagr_min": 10.0,
                            "pat_cagr_min": 0.0, "opm_min": 0.0, "pe_max": 100.0, "pb_max": 30.0,
                            "div_min": 0.0, "icr_min": 0.0},
    "Value Pick":          {"roe_min": 0.0,  "de_max": 2.0, "fcf_min": 0.0, "rev_cagr_min": 0.0,
                            "pat_cagr_min": 0.0, "opm_min": 0.0, "pe_max": 30.0, "pb_max": 5.0,
                            "div_min": 0.5, "icr_min": 0.0},
    "Growth Accelerator":  {"roe_min": 0.0,  "de_max": 2.0, "fcf_min": 0.0, "rev_cagr_min": 15.0,
                            "pat_cagr_min": 20.0, "opm_min": 0.0, "pe_max": 100.0, "pb_max": 30.0,
                            "div_min": 0.0, "icr_min": 0.0},
    "Dividend Champion":   {"roe_min": 0.0,  "de_max": 10.0, "fcf_min": 0.0, "rev_cagr_min": 0.0,
                            "pat_cagr_min": 0.0, "opm_min": 0.0, "pe_max": 100.0, "pb_max": 30.0,
                            "div_min": 2.0, "icr_min": 0.0},
    "Debt-Free Blue Chip": {"roe_min": 12.0, "de_max": 0.05, "fcf_min": 0.0, "rev_cagr_min": 0.0,
                            "pat_cagr_min": 0.0, "opm_min": 0.0, "pe_max": 100.0, "pb_max": 30.0,
                            "div_min": 0.0, "icr_min": 0.0},
    "Turnaround Watch":    {"roe_min": 0.0,  "de_max": 10.0, "fcf_min": 0.0, "rev_cagr_min": 10.0,
                            "pat_cagr_min": 0.0, "opm_min": 0.0, "pe_max": 100.0, "pb_max": 30.0,
                            "div_min": 0.0, "icr_min": 0.0},
}

# Session state for slider values
if "slider_vals" not in st.session_state:
    st.session_state.slider_vals = {
        "roe_min": 0.0, "de_max": 10.0, "fcf_min": -5000.0,
        "rev_cagr_min": 0.0, "pat_cagr_min": 0.0, "opm_min": 0.0,
        "pe_max": 100.0, "pb_max": 30.0, "div_min": 0.0, "icr_min": 0.0
    }

def load_data(year: str) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    try:
        yr_int = int(year.split("-")[0])
    except Exception:
        yr_int = 2024

    df_fr = pd.read_sql("SELECT * FROM financial_ratios WHERE year = ?", conn, params=(year,))
    df_c  = pd.read_sql("SELECT id as company_id, company_name FROM companies", conn)
    df_s  = pd.read_sql("SELECT company_id, broad_sector as sector FROM sectors", conn)
    df_mc = pd.read_sql("SELECT company_id, pe_ratio, pb_ratio, dividend_yield_pct FROM market_cap WHERE year = ?", conn, params=(yr_int,))
    df_pl = pd.read_sql("SELECT company_id, sales, operating_profit FROM profitandloss WHERE year = ?", conn, params=(year,))
    conn.close()

    df = df_fr.merge(df_c, on="company_id", how="left")
    df = df.merge(df_s, on="company_id", how="left")
    df = df.merge(df_mc, on="company_id", how="left")
    df = df.merge(df_pl, on="company_id", how="left", suffixes=("", "_pl"))

    # Compute OPM
    if "sales" in df.columns and "operating_profit" in df.columns:
        df["opm_pct"] = np.where(df["sales"] > 0, df["operating_profit"] / df["sales"] * 100, np.nan)
    else:
        df["opm_pct"] = np.nan

    if "sales_cagr_5yr" in df.columns:
        df["rev_cagr_5yr"] = df["sales_cagr_5yr"]
    else:
        df["rev_cagr_5yr"] = np.nan

    return df

st.title("🔍 Investment Screener")
st.caption("Filter across the Nifty 100 universe using key financial metrics.")

# ── Sidebar ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Screener Controls")
    year = st.selectbox("Financial Year", ["2024-03", "2023-03", "2022-03", "2021-03", "2020-03", "2019-03"], key="screener_year")

    st.markdown("---")
    st.markdown("### 🏷 Quick Presets")
    cols = st.columns(2)
    for i, preset_name in enumerate(PRESETS.keys()):
        if cols[i % 2].button(preset_name.split()[0], key=f"preset_{i}", use_container_width=True):
            st.session_state.slider_vals.update(PRESETS[preset_name])
            st.rerun()

    st.markdown("---")
    st.markdown("### 🎚 Metric Sliders")
    sv = st.session_state.slider_vals
    sv["roe_min"]      = st.slider("ROE min (%)",           0.0,  50.0, sv["roe_min"],      0.5)
    sv["de_max"]       = st.slider("D/E max",               0.0,  10.0, sv["de_max"],       0.1)
    sv["fcf_min"]      = st.slider("FCF min (Cr)",       -5000.0, 50000.0, sv["fcf_min"],   500.0)
    sv["rev_cagr_min"] = st.slider("Rev CAGR 5yr min (%)", -10.0, 50.0, sv["rev_cagr_min"], 1.0)
    sv["pat_cagr_min"] = st.slider("PAT CAGR 5yr min (%)", -10.0, 50.0, sv["pat_cagr_min"], 1.0)
    sv["opm_min"]      = st.slider("OPM min (%)",           0.0,  60.0, sv["opm_min"],      1.0)
    sv["pe_max"]       = st.slider("P/E max",               0.0, 100.0, sv["pe_max"],       1.0)
    sv["pb_max"]       = st.slider("P/B max",               0.0,  30.0, sv["pb_max"],       0.5)
    sv["div_min"]      = st.slider("Div Yield min (%)",     0.0,  10.0, sv["div_min"],      0.1)
    sv["icr_min"]      = st.slider("ICR min",               0.0,  50.0, sv["icr_min"],      0.5)

    st.markdown("---")
    if st.button("🔄 Reset All Filters", use_container_width=True):
        st.session_state.slider_vals = {
            "roe_min": 0.0, "de_max": 10.0, "fcf_min": -5000.0,
            "rev_cagr_min": 0.0, "pat_cagr_min": 0.0, "opm_min": 0.0,
            "pe_max": 100.0, "pb_max": 30.0, "div_min": 0.0, "icr_min": 0.0
        }
        st.rerun()

# ── Load & Filter ─────────────────────────────────────────────
df = load_data(year)
sv = st.session_state.slider_vals

mask = (
    (df["return_on_equity_pct"].fillna(-999)  >= sv["roe_min"]) &
    (df["debt_to_equity"].fillna(999)          <= sv["de_max"]) &
    (df["free_cash_flow_cr"].fillna(-999999)   >= sv["fcf_min"]) &
    (df["rev_cagr_5yr"].fillna(-999)           >= sv["rev_cagr_min"]) &
    (df["pat_cagr_5yr"].fillna(-999)           >= sv["pat_cagr_min"]) &
    (df["opm_pct"].fillna(-999)                >= sv["opm_min"]) &
    (df["pe_ratio"].fillna(999)                <= sv["pe_max"]) &
    (df["pb_ratio"].fillna(999)                <= sv["pb_max"]) &
    (df["dividend_yield_pct"].fillna(-999)     >= sv["div_min"]) &
    (df["interest_coverage"].fillna(-999)      >= sv["icr_min"])
)
result = df[mask].copy()

# ── Results Display ───────────────────────────────────────────
count = len(result)
color = "green" if 5 <= count <= 50 else ("orange" if count < 5 else "blue")
st.markdown(f"### :{color}[{count} companies match your filters]")

SHOW_COLS = ["company_id", "company_name", "sector",
             "composite_quality_score",
             "return_on_equity_pct", "debt_to_equity",
             "free_cash_flow_cr", "rev_cagr_5yr", "opm_pct",
             "pe_ratio", "pb_ratio", "dividend_yield_pct", "interest_coverage"]
present_cols = [c for c in SHOW_COLS if c in result.columns]
out_df = result[present_cols].reset_index(drop=True)
for col in out_df.select_dtypes(include="number").columns:
    out_df[col] = out_df[col].round(2)
out_df.index += 1

if not out_df.empty:
    st.dataframe(out_df, use_container_width=True, height=480)

    # CSV Download
    csv_buf = io.StringIO()
    out_df.to_csv(csv_buf, index=False)
    st.download_button(
        "⬇ Download Results as CSV",
        csv_buf.getvalue(),
        file_name=f"screener_results_{year}.csv",
        mime="text/csv"
    )
else:
    st.info("No companies match your current filters. Try relaxing the sliders.")
