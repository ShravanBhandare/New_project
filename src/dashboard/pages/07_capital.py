"""
pages/07_capital.py — Capital Allocation Treemap
Plotly treemap of 92 companies grouped by 8 capital allocation patterns
"""
import streamlit as st
import plotly.express as px
import pandas as pd
import numpy as np
import sqlite3
import os

st.set_page_config(page_title="Capital Allocation | Nifty 100", layout="wide")
DB_PATH = "data/nifty100.db"

@st.cache_data(ttl=600)
def load_capital_data(year: str = "2024-03") -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df_fr = pd.read_sql(
        "SELECT company_id, capital_allocation_pattern, free_cash_flow_cr, composite_quality_score "
        "FROM financial_ratios WHERE year = ?", conn, params=(year,)
    )
    df_c  = pd.read_sql("SELECT id as company_id, company_name FROM companies", conn)
    df_s  = pd.read_sql("SELECT company_id, broad_sector FROM sectors", conn)
    df_pl = pd.read_sql("SELECT company_id, sales FROM profitandloss WHERE year = ?", conn, params=(year,))
    conn.close()

    df = df_fr.merge(df_c, on="company_id", how="left")
    df = df.merge(df_s, on="company_id", how="left")
    df = df.merge(df_pl, on="company_id", how="left")
    df["sales"] = df["sales"].fillna(1000)
    df["capital_allocation_pattern"] = df["capital_allocation_pattern"].fillna("Unclassified")
    return df

st.title("💰 Capital Allocation Map")
st.caption("All 92 companies grouped by their capital allocation pattern. Size = Revenue.")

with st.sidebar:
    year = st.selectbox("Financial Year", ["2024-03", "2023-03", "2022-03"], key="capital_year")

df = load_capital_data(year)

# ── Treemap ───────────────────────────────────────────────────
st.subheader("🌳 Allocation Pattern Treemap")
plot_df = df.dropna(subset=["company_name"]).copy()
plot_df["sales_abs"] = plot_df["sales"].abs().clip(lower=100)

fig_tree = px.treemap(
    plot_df,
    path=["capital_allocation_pattern", "broad_sector", "company_name"],
    values="sales_abs",
    color="composite_quality_score",
    color_continuous_scale="RdYlGn",
    hover_data={"company_id": True, "free_cash_flow_cr": ":.0f", "sales_abs": ":,.0f"},
    color_continuous_midpoint=50,
)
fig_tree.update_traces(textinfo="label+value", textfont_size=12)
fig_tree.update_layout(height=580, margin=dict(t=30, l=5, r=5, b=5))
st.plotly_chart(fig_tree, use_container_width=True)

st.divider()

# ── Pattern Filter ────────────────────────────────────────────
st.subheader("🔍 Explore by Pattern")
patterns = ["All"] + sorted(df["capital_allocation_pattern"].dropna().unique().tolist())
selected_pattern = st.selectbox("Select Capital Allocation Pattern:", patterns)

if selected_pattern == "All":
    filtered = df.copy()
else:
    filtered = df[df["capital_allocation_pattern"] == selected_pattern].copy()

# Pattern distribution summary
counts = df["capital_allocation_pattern"].value_counts().reset_index()
counts.columns = ["Pattern", "Count"]
col1, col2 = st.columns([1, 2])
with col1:
    st.markdown(f"**{len(filtered)} companies** in selected pattern")
    st.dataframe(counts, use_container_width=True, height=280)
with col2:
    disp_cols = ["company_id", "company_name", "broad_sector",
                 "capital_allocation_pattern", "free_cash_flow_cr", "composite_quality_score"]
    disp_cols_present = [c for c in disp_cols if c in filtered.columns]
    tbl = filtered[disp_cols_present].reset_index(drop=True)
    for col in tbl.select_dtypes(include="number").columns:
        tbl[col] = tbl[col].round(2)
    st.dataframe(tbl, use_container_width=True, height=280)

# ── CSV Download ──────────────────────────────────────────────
csv_path = "output/capital_allocation.csv"
if os.path.exists(csv_path):
    st.divider()
    with open(csv_path, "rb") as f:
        st.download_button("⬇ Download capital_allocation.csv", f,
                           file_name="capital_allocation.csv", mime="text/csv")
