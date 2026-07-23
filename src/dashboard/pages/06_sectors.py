"""
pages/06_sectors.py — Sector Analysis
Bubble chart (X=Revenue, Y=ROE, size=MarketCap) + sector median KPI bar chart
"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import sqlite3

st.set_page_config(page_title="Sectors | Nifty 100", layout="wide")
DB_PATH = "data/nifty100.db"

@st.cache_data(ttl=600)
def load_sector_data(year: str = "2024-03") -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    try:
        yr_int = int(year.split("-")[0])
    except Exception:
        yr_int = 2024

    df_fr  = pd.read_sql("SELECT company_id, return_on_equity_pct, net_profit_margin_pct, debt_to_equity, sales_cagr_5yr, pat_cagr_5yr, composite_quality_score FROM financial_ratios WHERE year = ?", conn, params=(year,))
    df_c   = pd.read_sql("SELECT id as company_id, company_name FROM companies", conn)
    df_s   = pd.read_sql("SELECT company_id, broad_sector, sub_sector FROM sectors", conn)
    df_mc  = pd.read_sql("SELECT company_id, market_cap_crore, pe_ratio FROM market_cap WHERE year = ?", conn, params=(yr_int,))
    df_pl  = pd.read_sql("SELECT company_id, sales, operating_profit FROM profitandloss WHERE year = ?", conn, params=(year,))
    conn.close()

    df = df_fr.merge(df_c, on="company_id", how="left")
    df = df.merge(df_s, on="company_id", how="left")
    df = df.merge(df_mc, on="company_id", how="left")
    df = df.merge(df_pl, on="company_id", how="left")
    df["opm_pct"] = np.where(df["sales"] > 0, df["operating_profit"] / df["sales"] * 100, np.nan)
    return df

# ── UI ────────────────────────────────────────────────────────
st.title("🏭 Sector Analysis")

with st.sidebar:
    year = st.selectbox("Financial Year", ["2024-03", "2023-03", "2022-03", "2021-03"], key="sector_year")

df = load_sector_data(year)
all_sectors = sorted(df["broad_sector"].dropna().unique().tolist())

st.markdown("### 🌐 Nifty 100 Bubble Map")
st.caption("X = Revenue, Y = ROE, Bubble Size = Market Cap, Color = Sub-Sector")

selected_sector = st.selectbox("Filter by Sector (or 'All')", ["All"] + all_sectors)

if selected_sector == "All":
    plot_df = df.copy()
else:
    plot_df = df[df["broad_sector"] == selected_sector].copy()

plot_df = plot_df.dropna(subset=["sales", "return_on_equity_pct"])
plot_df["market_cap_crore"] = plot_df["market_cap_crore"].fillna(1000)
plot_df["market_cap_crore"] = plot_df["market_cap_crore"].clip(lower=100)

fig_bubble = px.scatter(
    plot_df,
    x="sales", y="return_on_equity_pct",
    size="market_cap_crore", color="sub_sector",
    hover_name="company_name",
    hover_data={"company_id": True, "broad_sector": True,
                "composite_quality_score": ":.1f",
                "sales": ":,.0f", "market_cap_crore": ":,.0f"},
    size_max=60,
    labels={"sales": "Revenue (₹ Cr)", "return_on_equity_pct": "ROE (%)"},
    color_discrete_sequence=px.colors.qualitative.Bold,
)
fig_bubble.update_layout(
    height=520, plot_bgcolor="rgba(0,0,0,0)",
    xaxis=dict(title="Revenue (₹ Crore)", tickformat=","),
    yaxis=dict(title="Return on Equity (%)"),
    legend=dict(orientation="h", yanchor="bottom", y=-0.35)
)
st.plotly_chart(fig_bubble, use_container_width=True)

st.divider()

# ── Sector Median KPI Bar Chart ───────────────────────────────
st.subheader(f"📊 Sector Median KPI Comparison")

KPI_MAP = {
    "ROE (%)":              "return_on_equity_pct",
    "D/E Ratio":            "debt_to_equity",
    "OPM (%)":              "opm_pct",
    "Rev CAGR 5yr (%)":     "sales_cagr_5yr",
    "PAT CAGR 5yr (%)":     "pat_cagr_5yr",
}

nifty_medians = {label: float(df[col].median()) for label, col in KPI_MAP.items() if col in df.columns}

if selected_sector != "All":
    sector_df = df[df["broad_sector"] == selected_sector]
    sector_medians = {label: float(sector_df[col].median()) for label, col in KPI_MAP.items() if col in sector_df.columns}

    kpi_labels = list(KPI_MAP.keys())
    nifty_vals  = [nifty_medians.get(k, 0) for k in kpi_labels]
    sector_vals = [sector_medians.get(k, 0) for k in kpi_labels]

    fig_bar = go.Figure()
    fig_bar.add_trace(go.Bar(name="Nifty 100 Median",       x=kpi_labels, y=nifty_vals,
                              marker_color="#90CAF9"))
    fig_bar.add_trace(go.Bar(name=f"{selected_sector} Median", x=kpi_labels, y=sector_vals,
                              marker_color="#1565C0"))
    fig_bar.update_layout(barmode="group", height=380, plot_bgcolor="rgba(0,0,0,0)",
                          yaxis_title="Median Value",
                          legend=dict(orientation="h", yanchor="bottom", y=1.02))
    st.plotly_chart(fig_bar, use_container_width=True)
else:
    # Show all-sector median table
    sector_stats = df.groupby("broad_sector")[list(KPI_MAP.values())].median().round(2)
    sector_stats.columns = list(KPI_MAP.keys())
    st.dataframe(sector_stats, use_container_width=True)
