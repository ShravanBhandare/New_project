import streamlit as st
import pandas as pd
from src.dashboard.utils.db import get_companies, get_company_details, get_financials_history
from src.dashboard.utils.charts import plot_financial_trend, plot_balance_sheet, plot_cash_flows

st.set_page_config(layout="wide")

# Styling
st.markdown("""
<style>
    .glass-card {
        background: rgba(22, 27, 34, 0.8);
        border-radius: 12px;
        padding: 20px;
        border: 1px solid rgba(48, 54, 65, 0.6);
        margin-bottom: 20px;
        color: #c9d1d9;
    }
    .metric-value {
        font-size: 26px;
        font-weight: 700;
        color: #58a6ff;
    }
    .metric-label {
        font-size: 13px;
        color: #8b949e;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
</style>
""", unsafe_allow_html=True)

st.title("🏢 Company Profile & History")

# Search and Select Company
companies_df = get_companies()
if not companies_df.empty:
    company_options = [f"{row['id']} - {row['company_name']}" for idx, row in companies_df.iterrows()]
    selected_option = st.selectbox("Select Company Ticker", company_options)
    selected_ticker = selected_option.split(" - ")[0]
else:
    selected_ticker = "TCS"

# Load Company Details
details = get_company_details(selected_ticker)
history = get_financials_history(selected_ticker)

if details:
    col_logo, col_desc = st.columns([1, 4])
    with col_logo:
        # Gracefully handle logo URLs
        logo_url = details.get('company_logo')
        if logo_url and logo_url != "nan":
            st.image(logo_url, width=150)
        else:
            st.markdown("### Logo Unavailable")
            
    with col_desc:
        st.markdown(f"## {details.get('company_name')} ({selected_ticker})")
        st.markdown(f"**Sector:** {details.get('broad_sector')} | **Sub-Sector:** {details.get('sub_sector')} | **Market Cap Category:** {details.get('market_cap_category')}")
        st.write(details.get('about_company', 'No description available.'))
        
        # Link buttons
        links_cols = st.columns(3)
        with links_cols[0]:
            web = details.get('website')
            if web and web != "nan":
                st.markdown(f"[🌐 Official Website]({web})")
        with links_cols[1]:
            nse = details.get('nse_profile')
            if nse and nse != "nan":
                st.markdown(f"[📊 NSE Profile]({nse})")
        with links_cols[2]:
            bse = details.get('bse_profile')
            if bse and bse != "nan":
                st.markdown(f"[📈 BSE Profile]({bse})")

    # Financial Multiples Cards
    st.markdown("### Latest Market Multiples")
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        pe = details.get('pe_ratio')
        pe_str = f"{pe:.2f}x" if pe else "N/A"
        st.markdown(f"<div class='glass-card'><div class='metric-label'>P/E Ratio</div><div class='metric-value'>{pe_str}</div></div>", unsafe_allow_html=True)
    with col2:
        pb = details.get('pb_ratio')
        pb_str = f"{pb:.2f}x" if pb else "N/A"
        st.markdown(f"<div class='glass-card'><div class='metric-label'>P/B Ratio</div><div class='metric-value'>{pb_str}</div></div>", unsafe_allow_html=True)
    with col3:
        ev_ebitda = details.get('ev_ebitda')
        eve = f"{ev_ebitda:.2f}x" if ev_ebitda else "N/A"
        st.markdown(f"<div class='glass-card'><div class='metric-label'>EV/EBITDA</div><div class='metric-value'>{eve}</div></div>", unsafe_allow_html=True)
    with col4:
        div_yield = details.get('dividend_yield_pct')
        dy = f"{div_yield:.2f}%" if div_yield else "0.00%"
        st.markdown(f"<div class='glass-card'><div class='metric-label'>Dividend Yield</div><div class='metric-value'>{dy}</div></div>", unsafe_allow_html=True)
    with col5:
        face = details.get('face_value')
        fv = f"₹{face:.0f}" if face else "N/A"
        st.markdown(f"<div class='glass-card'><div class='metric-label'>Face Value</div><div class='metric-value'>{fv}</div></div>", unsafe_allow_html=True)

    # Historical Financial Trends Charts
    st.markdown("### Historical Fundamentals")
    
    chart_tab, data_tab = st.tabs(["📉 Visual Trend Charts", "📋 Financial Statement Tables"])
    
    with chart_tab:
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            if not history['profitandloss'].empty:
                fig_pl = plot_financial_trend(history['profitandloss'])
                st.plotly_chart(fig_pl, use_container_width=True)
        with col_c2:
            if not history['balancesheet'].empty:
                fig_bs = plot_balance_sheet(history['balancesheet'])
                st.plotly_chart(fig_bs, use_container_width=True)
                
        if not history['cashflow'].empty:
            fig_cf = plot_cash_flows(history['cashflow'])
            st.plotly_chart(fig_cf, use_container_width=True)
            
    with data_tab:
        st.markdown("#### Profit & Loss Statement (Annual)")
        st.dataframe(history['profitandloss'], use_container_width=True)
        
        st.markdown("#### Balance Sheet (Annual)")
        st.dataframe(history['balancesheet'], use_container_width=True)
        
        st.markdown("#### Cash Flow Statement (Annual)")
        st.dataframe(history['cashflow'], use_container_width=True)
        
        st.markdown("#### Key Calculated Ratios")
        st.dataframe(history['ratios'], use_container_width=True)
else:
    st.error("Could not fetch company details.")
