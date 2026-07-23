"""
pages/01_home.py — Home screen
- 6 summary KPI tiles
- Sector breakdown donut chart (Plotly)
- Top-5 companies by composite quality score
- Year selector in sidebar
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from src.dashboard.utils.db import get_all_ratios_for_year, get_sectors

st.set_page_config(page_title="Home | Nifty 100 Analytics", layout="wide", initial_sidebar_state="expanded")

# ── Sidebar: year selector ───────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Filters")
    year_options = ["2024-03", "2023-03", "2022-03", "2021-03", "2020-03", "2019-03"]
    selected_year = st.selectbox("Select Year", year_options, index=0, key="home_year")

# ── Load data ────────────────────────────────────────────────
df = get_all_ratios_for_year(selected_year)

# ── Header ───────────────────────────────────────────────────
st.title("📊 Nifty 100 Analytics — Dashboard")
st.caption(f"Data for financial year: **{selected_year}** · {len(df)} companies loaded")
st.divider()

# ── 6 KPI tiles ──────────────────────────────────────────────
col1, col2, col3, col4, col5, col6 = st.columns(6)

avg_roe = df["return_on_equity_pct"].mean()
median_pe = df.get("pe_ratio", pd.Series(dtype=float)).median() if "pe_ratio" in df.columns else float("nan")
median_de = df["debt_to_equity"].median()
total_cos = len(df)
median_rev_cagr = df["sales_cagr_5yr"].median() if "sales_cagr_5yr" in df.columns else float("nan")
debt_free = int((df["debt_to_equity"].fillna(1) < 0.05).sum())

def kpi_tile(col, label, value, fmt="{:.1f}", suffix=""):
    try:
        display = fmt.format(float(value)) + suffix
    except Exception:
        display = "N/A"
    col.metric(label, display)

kpi_tile(col1, "⬆ Avg ROE",          avg_roe,        "{:.1f}", "%")
kpi_tile(col2, "📈 Median P/E",       median_pe,      "{:.1f}", "x")
kpi_tile(col3, "⚖ Median D/E",        median_de,      "{:.2f}", "")
kpi_tile(col4, "🏢 Companies",        total_cos,      "{:.0f}", "")
kpi_tile(col5, "🚀 Median Rev CAGR",  median_rev_cagr, "{:.1f}", "%")
kpi_tile(col6, "🟢 Debt-Free",        debt_free,      "{:.0f}", "")

st.divider()

# ── Charts row ───────────────────────────────────────────────
chart_col, top5_col = st.columns([1, 1])

with chart_col:
    st.subheader("🍩 Sector Breakdown")
    df_sec = get_sectors()
    sec_counts = df_sec.groupby("broad_sector").size().reset_index(name="count")
    fig = px.pie(sec_counts, names="broad_sector", values="count", hole=0.45,
                 color_discrete_sequence=px.colors.qualitative.Bold)
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(margin=dict(t=20, b=20, l=20, r=20), showlegend=False, height=380)
    st.plotly_chart(fig, use_container_width=True)

with top5_col:
    st.subheader("🏆 Top 5 by Composite Score")
    if "composite_quality_score" in df.columns:
        top5_cols = ["company_id", "company_name", "broad_sector",
                     "return_on_equity_pct", "debt_to_equity",
                     "composite_quality_score"]
        top5_cols_present = [c for c in top5_cols if c in df.columns]
        top5 = (df.sort_values("composite_quality_score", ascending=False)
                  .head(5)[top5_cols_present]
                  .reset_index(drop=True))
        top5.index += 1
        # Round numerics
        for col in top5.select_dtypes(include="number").columns:
            top5[col] = top5[col].round(2)
        st.dataframe(top5, use_container_width=True, height=220)
    else:
        st.info("Composite quality score not yet computed for this year.")

st.divider()

# ── Composite Score distribution bar chart ───────────────────
if "composite_quality_score" in df.columns and "broad_sector" in df.columns:
    st.subheader("📊 Composite Score Distribution by Sector")
    fig2 = px.box(df, x="broad_sector", y="composite_quality_score",
                  color="broad_sector", points="all",
                  color_discrete_sequence=px.colors.qualitative.Pastel)
    fig2.update_layout(
        xaxis_title="", yaxis_title="Composite Quality Score",
        showlegend=False, height=400,
        xaxis_tickangle=-30,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)"
    )
    st.plotly_chart(fig2, use_container_width=True)
