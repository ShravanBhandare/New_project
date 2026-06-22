import streamlit as st
import pandas as pd
import sqlite3
from src.dashboard.utils.db import get_connection
from src.dashboard.utils.charts import plot_radar_plotly

st.set_page_config(layout="wide")

st.title("👥 Peer Group Comparison")

# Load Peer Groups list
try:
    conn = get_connection()
    peer_groups = pd.read_sql("SELECT DISTINCT peer_group_name FROM peer_groups", conn)['peer_group_name'].tolist()
    conn.close()
except Exception as e:
    peer_groups = ["Private Banks", "IT Services", "Automobiles"]

if peer_groups:
    selected_group = st.selectbox("Select Peer Group to Compare", peer_groups)
    
    # Fetch members of selected group
    conn = get_connection()
    members_df = pd.read_sql("""
        SELECT company_id, is_benchmark 
        FROM peer_groups 
        WHERE peer_group_name = ?
    """, conn, params=(selected_group,))
    
    members = members_df['company_id'].tolist()
    benchmark_list = members_df[members_df['is_benchmark'] == 1]['company_id'].tolist()
    benchmark = benchmark_list[0] if benchmark_list else (members[0] if members else "None")
    
    # Load percentile rankings for this group
    rankings_query = """
        SELECT company_id, metric, value, percentile_rank, year
        FROM peer_percentiles
        WHERE peer_group = ?
    """
    rankings_df = pd.read_sql(rankings_query, conn, params=(selected_group,))
    conn.close()
    
    if not rankings_df.empty:
        # Side-by-side Comparison
        st.markdown(f"### Side-by-Side Comparison for {selected_group} (Benchmark: {benchmark})")
        
        # Pivot the rankings to show company as column, metric as index, and the actual value
        # Filter for latest year in the dataset
        latest_year = rankings_df['year'].max()
        st.markdown(f"Showing comparison for Financial Year: **{latest_year}**")
        
        group_latest = rankings_df[rankings_df['year'] == latest_year]
        
        # Pivot for actual values
        val_pivot = group_latest.pivot(index='metric', columns='company_id', values='value')
        
        # Pivot for percentile ranks
        rank_pivot = group_latest.pivot(index='metric', columns='company_id', values='percentile_rank')
        
        st.dataframe(val_pivot.round(2), use_container_width=True)
        
        # Radar Chart Visualization
        st.markdown("### Metric Percentile Rankings Radar")
        
        selected_company = st.selectbox("Select Company to Plot Radar", members)
        
        # Radar chart labels and company values
        radar_metrics = ['return_on_equity_pct', 'roce_percentage', 'net_profit_margin_pct', 'debt_to_equity', 'free_cash_flow_cr', 'pat_cagr_5yr', 'sales_cagr_5yr', 'fcf_cagr_5yr']
        radar_labels = ['ROE', 'ROCE', 'NPM', 'D/E (Inv)', 'FCF', 'PAT CAGR', 'Sales CAGR', 'FCF CAGR']
        
        # Filter rankings for this company and year
        comp_latest = group_latest[group_latest['company_id'] == selected_company]
        
        if not comp_latest.empty:
            comp_ranks = []
            for rm in radar_metrics:
                # Find the percentile rank for the metric
                m_row = comp_latest[comp_latest['metric'] == rm]
                if not m_row.empty:
                    comp_ranks.append(float(m_row.iloc[0]['percentile_rank']))
                else:
                    comp_ranks.append(0.0)
                    
            # Peer group average is 0.5 (representing the 50th percentile)
            group_avgs = [0.5] * len(radar_labels)
            
            fig = plot_radar_plotly(radar_labels, comp_ranks, selected_company, group_avgs)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No ranking data found for the selected company.")
    else:
        st.info("No comparative percentile ranks found for this group. Run make ratios or ratios calculator first.")
else:
    st.error("No peer groups found in the database.")
