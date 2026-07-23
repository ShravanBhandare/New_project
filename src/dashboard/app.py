"""
src/dashboard/app.py
Main Streamlit entry point.
Configures page layout and displays sidebar navigation to all 8 screens.
Run with: streamlit run src/dashboard/app.py
"""

import streamlit as st

st.set_page_config(
    page_title="Nifty 100 Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📊 Nifty 100 Analytics Platform")
st.markdown("""
Welcome to the **Nifty 100 Analytics Dashboard** — a comprehensive financial analysis platform
for all companies in the NSE Nifty 100 index.

---

### 🗺 Navigation Guide

Use the **sidebar** to navigate between the 8 analytical screens:

| Screen | Description |
|--------|-------------|
| 🏠 **Home** | Summary KPI tiles, sector breakdown, top-5 composite score |
| 🏢 **Profile** | Company-level KPIs, financials, charts and pros/cons |
| 🔍 **Screener** | Apply 6 investment preset filters across the Nifty 100 |
| 👥 **Peers** | Peer group comparison and percentile rankings |
| 📈 **Trends** | Historical metric trends for any company |
| 🏭 **Sectors** | Sector-level distribution and comparison |
| 💰 **Capital** | Capital allocation patterns (CFO/CFI/CFF classification) |
| 📁 **Reports** | Download Excel/CSV reports and radar chart images |

---

### 📦 Data Coverage
- **92 companies** in the Nifty 100 universe
- **12+ years** of financial history (2013–2024)
- **1,155 rows** in the financial ratios database
- **14+ computed KPIs** per company-year
""")

st.sidebar.markdown("## 📊 Nifty 100 Analytics")
st.sidebar.caption("Select a page above to get started.")
st.sidebar.divider()
st.sidebar.markdown("""
**Quick Links**
- [Home](Home)
- [Company Profile](Company_Profile)
- [Screener](Screener)
- [Peers](Peers)
""")
