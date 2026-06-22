import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from src.dashboard.utils.db import get_companies, get_financials_history

st.set_page_config(layout="wide")

st.title("📈 Historical Trend Analysis")

# Select Company
companies_df = get_companies()
if not companies_df.empty:
    company_options = [f"{row['id']} - {row['company_name']}" for idx, row in companies_df.iterrows()]
    selected_option = st.selectbox("Select Company Ticker", company_options)
    selected_ticker = selected_option.split(" - ")[0]
else:
    selected_ticker = "TCS"

# Load financial history
history = get_financials_history(selected_ticker)
pl_df = history['profitandloss']
bs_df = history['balancesheet']
cf_df = history['cashflow']
ratios_df = history['ratios']

# We will merge all dataframes to get a unified historical dataset for this company
merged_df = None
if not pl_df.empty:
    merged_df = pl_df[['year', 'sales', 'expenses', 'operating_profit', 'net_profit', 'eps']].copy()
if not bs_df.empty and merged_df is not None:
    merged_df = pd.merge(merged_df, bs_df[['year', 'equity_capital', 'reserves', 'borrowings', 'total_assets']], on='year', how='outer')
if not cf_df.empty and merged_df is not None:
    merged_df = pd.merge(merged_df, cf_df[['year', 'operating_activity', 'investing_activity', 'financing_activity']], on='year', how='outer')
if not ratios_df.empty and merged_df is not None:
    merged_df = pd.merge(merged_df, ratios_df[['year', 'return_on_equity_pct', 'debt_to_equity', 'interest_coverage']], on='year', how='outer')

if merged_df is not None and not merged_df.empty:
    merged_df = merged_df.sort_values(by='year')
    
    # Let's clean column names for readable selection
    metrics_map = {
        'sales': 'Sales / Revenue (Cr)',
        'expenses': 'Total Operating Expenses (Cr)',
        'operating_profit': 'Operating Profit / EBITDA (Cr)',
        'net_profit': 'Net Profit / PAT (Cr)',
        'eps': 'Earnings Per Share (EPS)',
        'equity_capital': 'Paid-up Equity Capital (Cr)',
        'reserves': 'Reserves & Surplus (Cr)',
        'borrowings': 'Total Debt / Borrowings (Cr)',
        'total_assets': 'Total Assets (Cr)',
        'operating_activity': 'Cash from Operations - CFO (Cr)',
        'investing_activity': 'Cash from Investing - CFI (Cr)',
        'financing_activity': 'Cash from Financing - CFF (Cr)',
        'return_on_equity_pct': 'Return on Equity - ROE (%)',
        'debt_to_equity': 'Debt-to-Equity (D/E)',
        'interest_coverage': 'Interest Coverage Ratio (ICR)'
    }
    
    available_cols = [c for c in metrics_map.keys() if c in merged_df.columns]
    select_options = {metrics_map[c]: c for c in available_cols}
    
    # Multiselect up to 3 metrics
    selected_labels = st.multiselect("Select up to 3 Metrics to Overlay", list(select_options.keys()), default=[list(select_options.keys())[0]])
    
    if selected_labels:
        fig = go.Figure()
        
        for label in selected_labels:
            col = select_options[label]
            series = merged_df[col]
            
            fig.add_trace(go.Scatter(
                x=merged_df['year'],
                y=series,
                mode='lines+markers',
                name=label,
                line=dict(width=2)
            ))
            
        fig.update_layout(
            title=f"Historical Metric Overlay - {selected_ticker}",
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font_color='#888888',
            xaxis_title="Year",
            yaxis_title="Value",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Display YoY Changes Table for the primary selected metric
        primary_label = selected_labels[0]
        primary_col = select_options[primary_label]
        
        st.markdown(f"#### YoY Growth & Trend Analysis: **{primary_label}**")
        
        analysis_df = merged_df[['year', primary_col]].copy()
        analysis_df['YoY Change (Cr)'] = analysis_df[primary_col].diff()
        analysis_df['YoY Growth (%)'] = (analysis_df[primary_col].pct_change() * 100.0).round(2)
        
        st.dataframe(analysis_df, use_container_width=True)
    else:
        st.info("Select one or more metrics to plot trends.")
else:
    st.error("No historical metrics found for this company.")
