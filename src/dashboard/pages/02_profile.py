"""
pages/02_profile.py — Company Profile screen
- Text search / autocomplete dropdown
- Company card: name, sector, sub-sector, ticker, about
- 6 KPI tiles (ROE, ROCE, NPM, D/E, Revenue CAGR 5yr, FCF)
- 10-year Revenue & Net Profit bar chart
- ROE & ROCE dual-axis line chart
- Pros and cons badges
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from src.dashboard.utils.db import (
    get_companies, get_ratios, get_pl, get_valuation, get_sectors, get_pros_cons
)

st.set_page_config(page_title="Company Profile | Nifty 100", layout="wide", initial_sidebar_state="expanded")

# ── Sidebar search ────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🔍 Company Search")
    companies = get_companies()
    company_list = [f"{row['id']} — {row['company_name']}" for _, row in companies.iterrows()]
    selected = st.selectbox("Type company name or ticker", [""] + company_list, index=0, key="profile_search")

if not selected:
    st.info("👈 Please select a company from the sidebar to view its profile.")
    st.stop()

ticker = selected.split("—")[0].strip()

# ── Load data ─────────────────────────────────────────────────
df_ratios = get_ratios(ticker)
df_pl     = get_pl(ticker)
df_sec    = get_sectors()
df_pros   = get_pros_cons(ticker)

sec_row   = df_sec[df_sec["company_id"] == ticker]
comp_row  = companies[companies["id"] == ticker]

if comp_row.empty:
    st.error(f"Ticker **{ticker}** not found — please try another.")
    st.stop()

company_name  = comp_row.iloc[0]["company_name"]
broad_sector  = sec_row.iloc[0]["broad_sector"]  if not sec_row.empty else "N/A"
sub_sector    = sec_row.iloc[0]["sub_sector"]    if not sec_row.empty else "N/A"

# ── Company card ──────────────────────────────────────────────
st.title(f"🏢 {company_name}")
card_col1, card_col2, card_col3 = st.columns([1, 1, 1])
card_col1.metric("NSE Ticker",    ticker)
card_col2.metric("Sector",        broad_sector)
card_col3.metric("Sub-Sector",    sub_sector)
st.divider()

# ── Latest year ratios ────────────────────────────────────────
latest_ratios = df_ratios.sort_values("year", ascending=False).iloc[0] if not df_ratios.empty else {}

def safe_get(row, col, fmt="{:.1f}", suffix=""):
    try:
        v = float(row.get(col, float("nan")) if isinstance(row, pd.Series) else row.get(col, float("nan")))
        return fmt.format(v) + suffix
    except Exception:
        return "N/A"

# ── 6 KPI tiles ───────────────────────────────────────────────
st.subheader(f"📌 Key Metrics — {latest_ratios.get('year', 'Latest')}")
k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("ROE",              safe_get(latest_ratios, "return_on_equity_pct",    suffix="%"))
k2.metric("ROCE",             safe_get(latest_ratios, "roce_percentage",          suffix="%"))
k3.metric("Net Profit Margin",safe_get(latest_ratios, "net_profit_margin_pct",   suffix="%"))
k4.metric("D/E Ratio",        safe_get(latest_ratios, "debt_to_equity",           fmt="{:.2f}"))
k5.metric("Revenue CAGR 5yr", safe_get(latest_ratios, "sales_cagr_5yr",          suffix="%"))
k6.metric("FCF (Cr)",         safe_get(latest_ratios, "free_cash_flow_cr",        fmt="{:,.0f}", suffix=" Cr"))

st.divider()

# ── 10-year Revenue & Net Profit bar chart ────────────────────
if not df_pl.empty:
    st.subheader("📊 10-Year Revenue & Net Profit")
    df_chart = df_pl.sort_values("year").tail(12).copy()   # up to last 12 rows
    fig = go.Figure()
    if "sales" in df_chart.columns:
        fig.add_trace(go.Bar(x=df_chart["year"], y=df_chart["sales"],
                             name="Revenue (Cr)", marker_color="#2196F3"))
    if "net_profit" in df_chart.columns:
        fig.add_trace(go.Bar(x=df_chart["year"], y=df_chart["net_profit"],
                             name="Net Profit (Cr)", marker_color="#4CAF50"))
    fig.update_layout(barmode="group", xaxis_title="Year", yaxis_title="₹ Crore",
                      height=380, plot_bgcolor="rgba(0,0,0,0)",
                      legend=dict(orientation="h", yanchor="bottom", y=1.02))
    st.plotly_chart(fig, use_container_width=True)

# ── ROE & ROCE dual-axis line chart ──────────────────────────
if not df_ratios.empty:
    st.subheader("📈 ROE & ROCE Over Time")
    df_r = df_ratios.sort_values("year").copy()
    fig2 = go.Figure()
    if "return_on_equity_pct" in df_r.columns:
        fig2.add_trace(go.Scatter(x=df_r["year"], y=df_r["return_on_equity_pct"],
                                  name="ROE %", mode="lines+markers",
                                  line=dict(color="#E91E63", width=2)))
    if "roce_percentage" in df_r.columns:
        fig2.add_trace(go.Scatter(x=df_r["year"], y=df_r["roce_percentage"],
                                  name="ROCE %", mode="lines+markers",
                                  line=dict(color="#FF9800", width=2, dash="dash"),
                                  yaxis="y2"))
    fig2.update_layout(
        xaxis_title="Year",
        yaxis=dict(title="ROE %", titlefont=dict(color="#E91E63")),
        yaxis2=dict(title="ROCE %", titlefont=dict(color="#FF9800"),
                    overlaying="y", side="right"),
        height=360, plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02)
    )
    st.plotly_chart(fig2, use_container_width=True)

st.divider()

# ── Pros & Cons badges ────────────────────────────────────────
st.subheader("✅ Pros & ❌ Cons")
pc_col1, pc_col2 = st.columns(2)

if not df_pros.empty:
    pros = df_pros[df_pros.get("type", pd.Series(dtype=str)).str.lower() == "pro"] if "type" in df_pros.columns else pd.DataFrame()
    cons = df_pros[df_pros.get("type", pd.Series(dtype=str)).str.lower() == "con"] if "type" in df_pros.columns else pd.DataFrame()
    text_col = "description" if "description" in df_pros.columns else (df_pros.columns[1] if len(df_pros.columns) > 1 else None)

    with pc_col1:
        if not pros.empty and text_col:
            for _, row in pros.iterrows():
                st.success(f"✅ {row.get(text_col, '')}")
        else:
            st.info("No pros data available.")

    with pc_col2:
        if not cons.empty and text_col:
            for _, row in cons.iterrows():
                st.error(f"❌ {row.get(text_col, '')}")
        else:
            st.info("No cons data available.")
else:
    st.info("No pros/cons data available for this company.")
