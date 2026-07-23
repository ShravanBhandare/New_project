"""
pages/04_peers.py — Peer Comparison with Scatterpolar radar chart
"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import sqlite3

st.set_page_config(page_title="Peer Comparison | Nifty 100", layout="wide")

DB_PATH = "data/nifty100.db"
PEER_GROUPS = ["Automobiles", "Consumer Finance", "FMCG", "IT Services",
               "Life Insurance", "Oil & Gas", "Pharmaceuticals",
               "Power & Utilities", "Private Banks", "Public Sector Banks", "Steel"]

RADAR_METRICS = ["return_on_equity_pct", "roce_percentage", "net_profit_margin_pct",
                 "debt_to_equity", "free_cash_flow_cr", "pat_cagr_5yr",
                 "sales_cagr_5yr", "composite_quality_score"]
RADAR_LABELS  = ["ROE%", "ROCE%", "NPM%", "D/E\n(inv)", "FCF\nScore",
                 "PAT CAGR", "Rev CAGR", "Composite"]

@st.cache_data(ttl=600)
def load_peer_data(group_name: str) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("""
        SELECT pg.company_id, c.company_name, pg.peer_group_name,
               fr.return_on_equity_pct, fr.roce_percentage, fr.net_profit_margin_pct,
               fr.debt_to_equity, fr.free_cash_flow_cr, fr.pat_cagr_5yr,
               fr.sales_cagr_5yr, fr.composite_quality_score, fr.interest_coverage,
               fr.asset_turnover, fr.earnings_per_share
        FROM peer_groups pg
        JOIN companies c ON pg.company_id = c.id
        LEFT JOIN financial_ratios fr ON pg.company_id = fr.company_id AND fr.year = '2024-03'
        WHERE pg.peer_group_name = ?
        ORDER BY fr.composite_quality_score DESC
    """, conn, params=(group_name,))
    conn.close()
    return df

def winsorise_series(s: pd.Series) -> pd.Series:
    p10, p90 = s.quantile(0.10), s.quantile(0.90)
    clipped = s.clip(lower=p10, upper=p90)
    rng = p90 - p10
    if rng == 0:
        return pd.Series([50.0] * len(s), index=s.index)
    return ((clipped - p10) / rng * 100).round(1)

def compute_radar_vals(row: pd.Series, df_group: pd.DataFrame) -> list:
    vals = []
    for i, m in enumerate(RADAR_METRICS):
        if m not in df_group.columns:
            vals.append(50.0)
            continue
        series = df_group[m].astype(float).dropna()
        if len(series) == 0:
            vals.append(50.0)
            continue
        norm = winsorise_series(series)
        if m == "debt_to_equity":
            norm = 100 - norm  # invert: lower D/E = better
        val = row.get(m)
        if pd.isna(val):
            vals.append(50.0)
        else:
            idx = df_group[m].astype(float).index
            if row.name in norm.index:
                vals.append(float(norm.loc[row.name]))
            else:
                vals.append(50.0)
    return vals

# ── UI ────────────────────────────────────────────────────────
st.title("👥 Peer Group Comparison")
st.caption("Radar chart and KPI comparison table for selected peer group.")

with st.sidebar:
    st.markdown("## Peer Group")
    group = st.selectbox("Select Group", PEER_GROUPS, key="peer_group")

df_peer = load_peer_data(group)
st.subheader(f"📊 {group} — {len(df_peer)} companies")

if df_peer.empty:
    st.info("No peer data found for this group.")
    st.stop()

# Company selector
company_list = df_peer["company_id"].tolist()
company_labels = [f"{row['company_id']} — {row['company_name']}" for _, row in df_peer.iterrows()]
selected_label = st.selectbox("Select company for radar focus:", company_labels)
selected_ticker = selected_label.split("—")[0].strip()
company_row = df_peer[df_peer["company_id"] == selected_ticker].iloc[0]

# ── Radar Chart ───────────────────────────────────────────────
col_radar, col_table = st.columns([1, 1.3])

with col_radar:
    st.subheader(f"🕸 {selected_ticker} vs {group} Average")

    # Compute normalised values for selected company and group average
    company_vals = []
    avg_vals = []
    for m in RADAR_METRICS:
        if m not in df_peer.columns:
            company_vals.append(50.0)
            avg_vals.append(50.0)
            continue
        series = df_peer[m].astype(float)
        norm = winsorise_series(series.dropna())
        if m == "debt_to_equity":
            norm = 100 - norm

        # Company value
        v = company_row.get(m)
        if pd.isna(v):
            company_vals.append(50.0)
        elif company_row.name in norm.index:
            company_vals.append(float(norm.loc[company_row.name]))
        else:
            company_vals.append(50.0)

        # Peer average
        avg_vals.append(float(norm.mean()) if len(norm) > 0 else 50.0)

    # Close the polygon
    company_vals_c = company_vals + [company_vals[0]]
    avg_vals_c     = avg_vals     + [avg_vals[0]]
    labels_c       = RADAR_LABELS + [RADAR_LABELS[0]]

    fig_radar = go.Figure()
    fig_radar.add_trace(go.Scatterpolar(
        r=company_vals_c, theta=labels_c,
        fill="toself", name=selected_ticker,
        line=dict(color="#2196F3", width=2),
        fillcolor="rgba(33,150,243,0.2)"
    ))
    fig_radar.add_trace(go.Scatterpolar(
        r=avg_vals_c, theta=labels_c,
        fill="toself", name=f"{group} Avg",
        line=dict(color="#FF5722", width=2, dash="dash"),
        fillcolor="rgba(255,87,34,0.1)"
    ))
    fig_radar.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=True, height=420,
        legend=dict(orientation="h", yanchor="bottom", y=-0.15)
    )
    st.plotly_chart(fig_radar, use_container_width=True)

# ── KPI Table ─────────────────────────────────────────────────
with col_table:
    st.subheader("📋 Peer Group KPI Table")
    disp_cols = ["company_id", "company_name",
                 "return_on_equity_pct", "roce_percentage", "net_profit_margin_pct",
                 "debt_to_equity", "free_cash_flow_cr", "pat_cagr_5yr",
                 "sales_cagr_5yr", "composite_quality_score", "interest_coverage"]
    cols_present = [c for c in disp_cols if c in df_peer.columns]
    tbl = df_peer[cols_present].copy().reset_index(drop=True)
    for col in tbl.select_dtypes(include="number").columns:
        tbl[col] = tbl[col].round(2)

    def highlight_benchmark(row):
        if row["company_id"] == selected_ticker:
            return ["background-color: #FFF3CD; font-weight: bold"] * len(row)
        return [""] * len(row)

    styled = tbl.style.apply(highlight_benchmark, axis=1)
    st.dataframe(styled, use_container_width=True, height=380)

# ── Download peer comparison ──────────────────────────────────
import os
peer_excel = "output/peer_comparison.xlsx"
if os.path.exists(peer_excel):
    st.divider()
    with open(peer_excel, "rb") as f:
        st.download_button("⬇ Download peer_comparison.xlsx", f,
                           file_name="peer_comparison.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
