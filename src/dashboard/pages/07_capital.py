import streamlit as st
import pandas as pd
import plotly.express as px
from src.dashboard.utils.db import get_connection
from src.analytics.cashflow_kpis import classify_capital_allocation

st.set_page_config(layout="wide")

st.title("🗺️ Capital Allocation Treemap")
st.markdown("Visualising corporate capital allocation profiles across the Nifty 100 universe based on Operating (CFO), Investing (CFI), and Financing (CFF) cash flow sign combinations.")

# Fetch cash flow histories
conn = get_connection()
query = """
    SELECT company_id, year, operating_activity, investing_activity, financing_activity
    FROM cashflow
    WHERE year != 'TTM'
"""
df = pd.read_sql(query, conn)
conn.close()

if not df.empty:
    # Get list of years
    available_years = sorted(df['year'].unique().tolist())
    selected_year = st.select_slider("Select Financial Year", available_years, value=available_years[-1])
    
    # Filter
    year_df = df[df['year'] == selected_year].copy()
    
    # Apply sign pattern classification
    patterns = []
    for idx, row in year_df.iterrows():
        cfo = row['operating_activity'] if not pd.isna(row['operating_activity']) else 0.0
        cfi = row['investing_activity'] if not pd.isna(row['investing_activity']) else 0.0
        cff = row['financing_activity'] if not pd.isna(row['financing_activity']) else 0.0
        patterns.append(classify_capital_allocation(cfo, cfi, cff))
        
    year_df['capital_pattern'] = patterns
    
    # Let's count totals
    st.markdown(f"### Capital Profiles for Year: **{selected_year}**")
    
    # Draw Treemap: path = ['capital_pattern', 'company_id'], values = abs(operating_activity)
    # Absolute CFO gives us an indication of scale
    year_df['cfo_scale'] = year_df['operating_activity'].apply(lambda x: max(abs(x), 10.0))
    
    fig = px.treemap(
        year_df,
        path=['capital_pattern', 'company_id'],
        values='cfo_scale',
        hover_data=['operating_activity', 'investing_activity', 'financing_activity'],
        color='capital_pattern',
        template="plotly_dark"
    )
    
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font_color='#888888',
        margin=dict(l=10, r=10, t=30, b=10)
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Show summary stats table
    st.markdown("### Profile Summaries")
    summary = year_df.groupby('capital_pattern').size().reset_index(name='Company Count')
    st.dataframe(summary, use_container_width=True)
else:
    st.error("No cash flow data loaded in SQLite.")
