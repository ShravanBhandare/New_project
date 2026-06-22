import sqlite3
import pandas as pd
import numpy as np
import os
import logging
import matplotlib
matplotlib.use('Agg') # Use non-interactive backend
import matplotlib.pyplot as plt
from typing import List, Dict, Any

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

DB_PATH = "data/nifty100.db"
RADAR_DIR = "reports/radar_charts"

def get_peer_comparison_data() -> pd.DataFrame:
    """Fetch the latest metrics for all companies to perform peer group comparisons."""
    from src.analytics.screener.engine import get_latest_screener_data
    df = get_latest_screener_data()
    return df

def generate_radar_chart(company_id: str, company_name: str, group_name: str, 
                         labels: list, company_values: list, group_avg_values: list):
    """
    Generate a polar radar chart comparing the company's percentile ranks vs group average (0.5).
    Saves the output to reports/radar_charts/<company_id>_radar.png.
    """
    os.makedirs(RADAR_DIR, exist_ok=True)
    
    num_vars = len(labels)
    
    # Compute angle for each axis
    angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
    
    # The plot is circular, so we must close the loop
    company_values = company_values + [company_values[0]]
    group_avg_values = group_avg_values + [group_avg_values[0]]
    angles = angles + [angles[0]]
    labels_closed = labels + [labels[0]]
    
    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    
    # Draw one axe per variable and add labels
    plt.xticks(angles[:-1], labels, color='grey', size=8)
    
    # Draw ylabels
    ax.set_rlabel_position(0)
    plt.yticks([0.2, 0.4, 0.6, 0.8, 1.0], ["20%", "40%", "60%", "80%", "100%"], color="grey", size=7)
    plt.ylim(0, 1.0)
    
    # Plot Company Data
    ax.plot(angles, company_values, linewidth=2, linestyle='solid', label=company_id, color='#1f77b4')
    ax.fill(angles, company_values, color='#1f77b4', alpha=0.25)
    
    # Plot Group Average Data
    ax.plot(angles, group_avg_values, linewidth=1, linestyle='dashed', label='Peer Avg', color='#ff7f0e')
    ax.fill(angles, group_avg_values, color='#ff7f0e', alpha=0.05)
    
    # Styling
    ax.set_title(f"{company_id} - {company_name}\nvs {group_name} Group", size=11, weight='bold', color='#333333', y=1.1)
    ax.legend(loc='upper right', bbox_to_anchor=(0.1, 0.1), fontsize=8)
    
    plt.tight_layout()
    output_path = os.path.join(RADAR_DIR, f"{company_id}_radar.png")
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

def run_peer_engine():
    logger.info("Running Peer Comparison Engine...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Fetch peer groups mapping
    # Columns: id, peer_group_name, company_id, is_benchmark
    peer_df = pd.read_sql("SELECT peer_group_name, company_id, is_benchmark FROM peer_groups", conn)
    if peer_df.empty:
        logger.error("No peer groups found in the database. Ensure peer_groups table is populated.")
        conn.close()
        return
        
    # Get latest data for all companies
    data_df = get_peer_comparison_data()
    
    # We will compute ranks for 20 metrics
    metrics = [
        'return_on_equity_pct', 'roce_percentage', 'net_profit_margin_pct',
        'debt_to_equity', 'free_cash_flow_cr', 'pat_cagr_5yr', 'sales_cagr_5yr', 'fcf_cagr_5yr',
        'sales', 'net_profit', 'pe_ratio', 'pb_ratio', 'ev_ebitda', 'dividend_yield_pct',
        'dividend_payout_ratio_pct', 'capex_cr', 'book_value_per_share', 'asset_turnover',
        'cfo_pat_ratio'
    ]
    
    # We will build peer comparison records for SQLite
    peer_percentile_records = []
    
    # We will write peer comparisons to Excel
    excel_path = "output/peer_comparison.xlsx"
    os.makedirs(os.path.dirname(excel_path), exist_ok=True)
    
    # Group names list
    group_names = peer_df['peer_group_name'].unique()
    
    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        for group in group_names:
            # Get members of this group
            members = peer_df[peer_df['peer_group_name'] == group]['company_id'].tolist()
            
            # Filter data for this group
            group_data = data_df[data_df['company_id'].isin(members)].copy()
            if group_data.empty:
                continue
                
            # Compute percentile ranks for this group
            rank_df = group_data[['company_id', 'company_name', 'sector', 'year']].copy()
            
            for m in metrics:
                if m in group_data.columns:
                    series = group_data[m]
                    # Handle empty/NaN values
                    valid_series = series.fillna(0.0)
                    
                    # For D/E, PE, PB, EV/EBITDA, lower values are better, so we invert rankings
                    lower_is_better = m in ['debt_to_equity', 'pe_ratio', 'pb_ratio', 'ev_ebitda']
                    
                    if lower_is_better:
                        # Rank ascending but invert the percentile rank
                        ranks = valid_series.rank(method='min', pct=True)
                        percentile_ranks = 1.0 - ranks
                    else:
                        percentile_ranks = valid_series.rank(method='min', pct=True)
                        
                    rank_df[f"{m}_value"] = valid_series
                    rank_df[f"{m}_pct_rank"] = percentile_ranks
                    
                    # Store to records for DB
                    for idx, row in rank_df.iterrows():
                        peer_percentile_records.append((
                            row['company_id'], group, m, float(valid_series.loc[idx]), float(percentile_ranks.loc[idx]), str(row['year'])
                        ))
                        
            # Format and save this group to Excel sheet
            # Select column layout for display: value next to percentile rank
            sheet_cols = ['company_id', 'company_name']
            for m in metrics:
                if f"{m}_value" in rank_df.columns:
                    sheet_cols.extend([f"{m}_value", f"{m}_pct_rank"])
                    
            output_df = rank_df[sheet_cols].copy()
            # Round values
            for col in output_df.columns:
                if col not in ['company_id', 'company_name']:
                    output_df[col] = output_df[col].round(2)
                    
            sheet_name = group[:30] # Excel limit 31 chars
            output_df.to_excel(writer, sheet_name=sheet_name, index=False)
            logger.info(f"Generated comparison sheet for peer group: {group}")
            
            # Generate radar charts for each company in the group
            radar_metrics = ['return_on_equity_pct', 'roce_percentage', 'net_profit_margin_pct', 'debt_to_equity', 'free_cash_flow_cr', 'pat_cagr_5yr', 'sales_cagr_5yr', 'fcf_cagr_5yr']
            radar_labels = ['ROE', 'ROCE', 'NPM', 'D/E (Inv)', 'FCF', 'PAT CAGR', 'Sales CAGR', 'FCF CAGR']
            
            for idx, row in rank_df.iterrows():
                comp_id = row['company_id']
                comp_name = row['company_name']
                
                # Gather company ranks
                comp_ranks = []
                for rm in radar_metrics:
                    comp_ranks.append(float(row[f"{rm}_pct_rank"]))
                    
                # Group average rank is always 0.5 (representing the average percentile of the cohort)
                group_avgs = [0.5] * len(radar_metrics)
                
                generate_radar_chart(comp_id, comp_name, group, radar_labels, comp_ranks, group_avgs)
                
    # 2. Write to DB peer_percentiles table
    logger.info("Writing rankings to peer_percentiles table in SQLite...")
    cursor.execute("DELETE FROM peer_percentiles;")
    
    insert_query = """
    INSERT INTO peer_percentiles (
        company_id, peer_group, metric, value, percentile_rank, year
    ) VALUES (?, ?, ?, ?, ?, ?)
    """
    
    cursor.executemany(insert_query, peer_percentile_records)
    conn.commit()
    
    # Count rows
    cursor.execute("SELECT COUNT(*) FROM peer_percentiles")
    row_count = cursor.fetchone()[0]
    logger.info(f"Loaded {row_count} percentile rows in SQLite peer_percentiles table successfully.")
    
    conn.close()
    logger.info(f"Peer comparison engine completed successfully. Radar charts saved at: {RADAR_DIR}")

if __name__ == "__main__":
    run_peer_engine()
