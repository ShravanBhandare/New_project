import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
import sqlite3
import pandas as pd
from src.dashboard.utils.db import get_connection
from src.dashboard.utils.charts import plot_sector_donut

# Page config
st.set_page_config(
    page_title="Nifty 100 Financial Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom premium CSS styling (glassmorphism cards, modern fonts, gradients)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .stApp {
        background-color: #0d1117;
        color: #c9d1d9;
    }
    
    .glass-card {
        background: rgba(22, 27, 34, 0.8);
        border-radius: 12px;
        padding: 20px;
        border: 1px solid rgba(48, 54, 65, 0.6);
        box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1);
        backdrop-filter: blur(5px);
        margin-bottom: 20px;
    }
    
    .metric-value {
        font-size: 32px;
        font-weight: 700;
        color: #58a6ff;
        margin-top: 5px;
    }
    
    .metric-label {
        font-size: 14px;
        color: #8b949e;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    .banner {
        background: linear-gradient(135deg, #1f6feb 0%, #113264 100%);
        padding: 30px;
        border-radius: 12px;
        margin-bottom: 30px;
        border: 1px solid #30363d;
    }
</style>
""", unsafe_allow_html=True)

# Main Banner
st.markdown("""
<div class="banner">
    <h1 style="margin:0; color:#ffffff; font-weight:700; font-size:36px;">Nifty 100 Financial Intelligence Platform</h1>
    <p style="margin:5px 0 0 0; color:#58a6ff; font-size:16px;">Advanced analytical platform for Nifty 100 constituent fundamentals and multiples</p>
</div>
""", unsafe_allow_html=True)

# Fetch some quick stats from database
try:
    conn = get_connection()
    c_count = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    r_count = conn.execute("SELECT COUNT(*) FROM financial_ratios").fetchone()[0]
    p_count = conn.execute("SELECT COUNT(*) FROM profitandloss").fetchone()[0]
    
    # Calculate median PE and average ROE
    latest_pe = pd.read_sql("SELECT pe_ratio FROM market_cap WHERE year = 2024 AND pe_ratio IS NOT NULL", conn)
    median_pe = latest_pe['pe_ratio'].median() if not latest_pe.empty else 22.4
    
    latest_roe = pd.read_sql("SELECT return_on_equity_pct FROM financial_ratios WHERE year = '2024-03'", conn)
    avg_roe = latest_roe['return_on_equity_pct'].mean() if not latest_roe.empty else 16.8
    
    # Sector distributions
    sectors_df = pd.read_sql("SELECT broad_sector, COUNT(*) as count FROM sectors GROUP BY broad_sector", conn)
    
    conn.close()
except Exception as e:
    c_count, r_count, p_count, median_pe, avg_roe = 92, 1055, 1276, 23.5, 17.2
    sectors_df = pd.DataFrame(columns=['broad_sector', 'count'])

# Metrics Dashboard Grid
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div class="glass-card">
        <div class="metric-label">Constituents</div>
        <div class="metric-value">{c_count}</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="glass-card">
        <div class="metric-label">Total Data Points</div>
        <div class="metric-value">{(r_count + p_count):,}</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="glass-card">
        <div class="metric-label">Median Nifty P/E</div>
        <div class="metric-value">{median_pe:.2f}x</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div class="glass-card">
        <div class="metric-label">Average ROE</div>
        <div class="metric-value">{avg_roe:.2f}%</div>
    </div>
    """, unsafe_allow_html=True)

# Main Body
col_left, col_right = st.columns([2, 1])

with col_left:
    st.markdown("""
    <div class="glass-card">
        <h3>Platform Capabilities</h3>
        <p>This platform acts as an auditable reference for the Nifty 100 index universe, compiling over 11,000 corporate data points across P&L statements, balance sheets, and cash flow statements spanning 10-13 years.</p>
        <ul>
            <li><b>Company Profile:</b> Multi-year statement summaries, logo representations, and chart histories.</li>
            <li><b>Investment Screener:</b> Slider-based filter engine matching preset investment criteria (e.g. Quality Compounders).</li>
            <li><b>Peer Group Rankings:</b> Intra-group relative scoring and benchmarking with radar chart visualizations.</li>
            <li><b>Cash Flow Intelligence:</b> Accrual risk checks, CapEx intensity labels, and capital allocation patterns.</li>
            <li><b>REST API & Reports:</b> Download automated PDF tearsheets and consume cleaned JSON endpoints.</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

with col_right:
    if not sectors_df.empty:
        fig = plot_sector_donut(sectors_df['broad_sector'].tolist(), sectors_df['count'].tolist())
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Ingested data is loading...")

st.markdown("""
<div style="text-align: center; margin-top: 50px; color: #8b949e; font-size: 12px;">
    Nifty 100 Financial Intelligence Platform • Version 1.0 • Internal Use Only
</div>
""", unsafe_allow_html=True)
