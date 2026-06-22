import streamlit as st
import pandas as pd
import plotly.express as px
from src.dashboard.utils.db import get_connection

st.set_page_config(layout="wide")

st.title("🏭 Sector-wise Benchmarking")

# Fetch sector list and company metrics
conn = get_connection()
query = """
    SELECT 
        c.id as company_id, c.company_name, s.broad_sector as sector,
        f.return_on_equity_pct as roe, f.sales, f.debt_to_equity,
        m.market_cap_crore
    FROM companies c
    JOIN sectors s ON c.id = s.company_id
    JOIN financial_ratios f ON c.id = f.company_id
    JOIN market_cap m ON c.id = m.company_id AND m.year = 2024
    WHERE f.year = '2024-03'
"""
df = pd.read_sql(query, conn)
conn.close()

if not df.empty:
    sectors = ["All Sectors"] + sorted(df['sector'].unique().tolist())
    selected_sector = st.selectbox("Filter by Sector", sectors)
    
    # Filter
    if selected_sector == "All Sectors":
        plot_df = df.copy()
    else:
        plot_df = df[df['sector'] == selected_sector].copy()
        
    # Bubble Chart: Sales vs ROE, size = market cap
    st.markdown("### Sector Bubble Matrix (Sales vs ROE)")
    st.markdown("The size of the bubble corresponds to the company's **Market Capitalization**.")
    
    # Clean NaN values
    plot_df = plot_df.dropna(subset=['sales', 'roe', 'market_cap_crore'])
    # Avoid negative values for sizing
    plot_df['mcap_size'] = plot_df['market_cap_crore'].apply(lambda x: max(x, 10.0))
    
    fig = px.scatter(
        plot_df,
        x="sales",
        y="roe",
        size="mcap_size",
        color="sector",
        hover_name="company_id",
        hover_data=["company_name", "market_cap_crore", "debt_to_equity"],
        labels={
            "sales": "Annual Sales (Cr)",
            "roe": "Return on Equity (ROE %)",
            "sector": "Sector"
        },
        template="plotly_dark"
    )
    
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font_color='#888888',
        margin=dict(l=40, r=40, t=40, b=40)
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Median Metrics per Sector
    st.markdown("### Sector Median Fundamentals (2024)")
    medians_df = df.groupby('sector')[['roe', 'sales', 'debt_to_equity', 'market_cap_crore']].median().reset_index()
    
    # Round
    for col in medians_df.select_dtypes(include=['number']).columns:
        medians_df[col] = medians_df[col].round(2)
        
    st.dataframe(medians_df, use_container_width=True)
else:
    st.error("No benchmark data loaded in SQLite. Run make load and populate ratios first.")
