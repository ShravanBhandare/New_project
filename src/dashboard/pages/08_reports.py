"""
pages/08_reports.py — Annual Reports & Report Downloads
Company search → annual report PDF links; download buttons for Excel/CSV outputs
"""
import streamlit as st
import pandas as pd
import sqlite3
import os

st.set_page_config(page_title="Reports | Nifty 100", layout="wide")
DB_PATH = "data/nifty100.db"

@st.cache_data(ttl=600)
def load_companies():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT id, company_name FROM companies ORDER BY company_name", conn)
    conn.close()
    return df

@st.cache_data(ttl=600)
def load_annual_reports(ticker: str) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql(
            "SELECT company_id, Year, Annual_Report FROM documents WHERE company_id = ? ORDER BY Year DESC",
            conn, params=(ticker,)
        )
    except Exception:
        df = pd.DataFrame(columns=["company_id", "Year", "Annual_Report"])
    conn.close()
    return df

st.title("📁 Reports & Annual Filings")
st.caption("Download analytical reports and access BSE annual report PDF links.")

# ── Company Annual Reports ────────────────────────────────────
st.subheader("📄 Company Annual Reports")
companies = load_companies()
company_list = [f"{r['id']} — {r['company_name']}" for _, r in companies.iterrows()]
selected = st.selectbox("Select Company:", [""] + company_list, key="reports_company")

if selected:
    ticker = selected.split("—")[0].strip()
    df_docs = load_annual_reports(ticker)

    if df_docs.empty:
        st.warning(f"No annual report links found for **{ticker}**.")
    else:
        st.markdown(f"**{len(df_docs)} annual reports found for {ticker}:**")
        for _, row in df_docs.iterrows():
            year_label = int(row["Year"]) if not pd.isna(row["Year"]) else "N/A"
            url = str(row.get("Annual_Report", ""))

            if url.startswith("http"):
                st.markdown(f"📎 **FY {year_label}** → [View Annual Report PDF]({url})")
            else:
                col1, col2 = st.columns([1, 3])
                col1.markdown(f"**FY {year_label}**")
                col2.error("🚫 Report unavailable")

st.divider()

# ── Generated Output Downloads ────────────────────────────────
st.subheader("⬇ Download Generated Reports")

REPORT_FILES = [
    ("output/screener_output.xlsx",         "📊 Screener Output (6 preset sheets)",                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    ("output/peer_comparison.xlsx",         "👥 Peer Comparison (11 group sheets)",                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    ("output/valuation_summary.xlsx",       "💹 Valuation Summary (92 companies)",                 "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    ("output/valuation_flags.csv",          "⚠️ Valuation Flags (Caution & Discount only)",       "text/csv"),
    ("output/capital_allocation.csv",       "💰 Capital Allocation Patterns",                      "text/csv"),
    ("output/cashflow_intelligence.xlsx",   "🔄 Cash Flow Intelligence",                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    ("output/distress_alerts.csv",          "🚨 Distress Alerts",                                  "text/csv"),
    ("output/pros_cons_generated.csv",      "✅ Auto-Generated Pros & Cons",                       "text/csv"),
    ("output/analysis_parsed.csv",          "📈 Analysis Text Parsed (CAGR/ROE)",                  "text/csv"),
    ("output/ratio_edge_cases.log",         "⚠️ Ratio Edge Cases Log",                             "text/plain"),
]

cols = st.columns(2)
for i, (path, label, mime) in enumerate(REPORT_FILES):
    with cols[i % 2]:
        if os.path.exists(path):
            with open(path, "rb") as f:
                st.download_button(label, f, file_name=os.path.basename(path), mime=mime,
                                   use_container_width=True)
        else:
            st.warning(f"{label} — not yet generated.")

st.divider()

# ── Radar Charts Preview ──────────────────────────────────────
st.subheader("🕸 Radar Chart Gallery")
radar_dir = "reports/radar_charts"
if os.path.exists(radar_dir):
    charts = sorted([f for f in os.listdir(radar_dir) if f.endswith("_radar.png")])
    if charts:
        preview_company = st.selectbox("Preview radar chart for:", [c.replace("_radar.png", "") for c in charts])
        if preview_company:
            chart_path = os.path.join(radar_dir, f"{preview_company}_radar.png")
            if os.path.exists(chart_path):
                st.image(chart_path, caption=f"{preview_company} Radar Chart", width=500)
    else:
        st.info("No radar charts found. Run `python -m src.analytics.peer` to generate them.")
else:
    st.info("Radar charts directory not found.")
