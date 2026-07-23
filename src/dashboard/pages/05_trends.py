"""
pages/05_trends.py — Historical Trend Analysis
Multi-metric selector (up to 3), 10-year line chart, YoY % change annotations
"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import sqlite3

st.set_page_config(page_title="Trends | Nifty 100", layout="wide")
DB_PATH = "data/nifty100.db"

METRIC_OPTIONS = {
    "ROE (%)":                    "return_on_equity_pct",
    "Net Profit Margin (%)":      "net_profit_margin_pct",
    "D/E Ratio":                  "debt_to_equity",
    "Revenue CAGR 5yr (%)":       "sales_cagr_5yr",
    "PAT CAGR 5yr (%)":           "pat_cagr_5yr",
    "Composite Quality Score":    "composite_quality_score",
    "Interest Coverage":          "interest_coverage",
    "Asset Turnover":             "asset_turnover",
    "EPS":                        "earnings_per_share",
    "Book Value per Share":       "book_value_per_share",
}

@st.cache_data(ttl=600)
def load_companies():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT id, company_name FROM companies ORDER BY company_name", conn)
    conn.close()
    return df

@st.cache_data(ttl=600)
def load_ratios(ticker: str) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM financial_ratios WHERE company_id = ? ORDER BY year", conn, params=(ticker,))
    conn.close()
    return df

# ── Sidebar ───────────────────────────────────────────────────
companies = load_companies()
company_list = [f"{r['id']} — {r['company_name']}" for _, r in companies.iterrows()]

with st.sidebar:
    st.markdown("## 📈 Trend Settings")
    selected = st.selectbox("Select Company", [""] + company_list, key="trends_company")
    selected_labels = st.multiselect(
        "Select Metrics (up to 3)",
        list(METRIC_OPTIONS.keys()),
        default=["ROE (%)", "Net Profit Margin (%)"],
        max_selections=3
    )

st.title("📈 Historical Trend Analysis")

if not selected:
    st.info("👈 Please select a company from the sidebar.")
    st.stop()

ticker = selected.split("—")[0].strip()
df = load_ratios(ticker)

if df.empty:
    st.error(f"Ticker **{ticker}** not found — please try another.")
    st.stop()

n_years = df["year"].nunique()
if n_years < 10:
    st.info(f"ℹ️ Note: Only {n_years} years of data available for {ticker}.")

company_name = companies[companies["id"] == ticker]["company_name"].values
company_name = company_name[0] if len(company_name) > 0 else ticker
st.subheader(f"🏢 {company_name} ({ticker})")

if not selected_labels:
    st.warning("Please select at least one metric from the sidebar.")
    st.stop()

# ── Multi-metric Line Chart ───────────────────────────────────
fig = go.Figure()
COLORS = ["#2196F3", "#4CAF50", "#FF5722"]

for i, label in enumerate(selected_labels):
    col_name = METRIC_OPTIONS[label]
    if col_name not in df.columns:
        st.warning(f"Metric '{label}' not available for this company.")
        continue

    sub = df[["year", col_name]].dropna()
    if sub.empty:
        continue

    vals = sub[col_name].astype(float)
    years = sub["year"].tolist()

    # YoY % change
    yoy = vals.pct_change() * 100
    texts = []
    for j, (y, pct) in enumerate(zip(years, yoy)):
        if j == 0 or np.isnan(pct):
            texts.append("")
        else:
            sign = "+" if pct >= 0 else ""
            texts.append(f"{sign}{pct:.1f}%")

    fig.add_trace(go.Scatter(
        x=years, y=vals.tolist(),
        mode="lines+markers+text",
        name=label,
        line=dict(color=COLORS[i % len(COLORS)], width=2),
        marker=dict(size=7),
        text=texts,
        textposition="top center",
        textfont=dict(size=9, color=COLORS[i % len(COLORS)])
    ))

fig.update_layout(
    title=f"{ticker} — {', '.join(selected_labels)} over time",
    xaxis_title="Year", yaxis_title="Value",
    height=480, plot_bgcolor="rgba(0,0,0,0)",
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
    hovermode="x unified"
)
fig.update_xaxes(tickangle=-30)
st.plotly_chart(fig, use_container_width=True)

# ── Data Table ────────────────────────────────────────────────
st.subheader("📊 Raw Data Table")
metric_cols = [METRIC_OPTIONS[l] for l in selected_labels if METRIC_OPTIONS[l] in df.columns]
tbl_cols = ["year"] + metric_cols
tbl = df[tbl_cols].copy().reset_index(drop=True)
for col in tbl.select_dtypes(include="number").columns:
    tbl[col] = tbl[col].round(2)
st.dataframe(tbl, use_container_width=True)
