import sqlite3
import pandas as pd
import numpy as np
import os
import json
import logging
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

DB_PATH = "data/nifty100.db"

def run_clustering_and_analytics():
    logger.info("Initializing Clustering and Outlier Analysis...")
    conn = sqlite3.connect(DB_PATH)
    
    # 1. Fetch latest screener and ratios data
    # We will join companies, financial_ratios, sectors, market_cap and get CAGRs
    from src.analytics.screener.engine import get_latest_screener_data
    df = get_latest_screener_data()
    
    # We also want to make sure we have operating_profit_margin_pct (OPM), asset_turnover, and roce_percentage
    # Let's get OPM and asset_turnover for latest year from financial_ratios
    ratios_query = """
    SELECT company_id, year, operating_profit_margin_pct as opm, asset_turnover
    FROM financial_ratios
    """
    ratios_df = pd.read_sql(ratios_query, conn)
    latest_ratios = ratios_df.sort_values('year').groupby('company_id').last().reset_index()
    opm_map = dict(zip(latest_ratios['company_id'], latest_ratios['opm']))
    at_map = dict(zip(latest_ratios['company_id'], latest_ratios['asset_turnover']))
    df['operating_profit_margin_pct'] = df['company_id'].map(opm_map).fillna(0.0)
    df['asset_turnover'] = df['company_id'].map(at_map).fillna(0.0)
    
    # Fetch roce_percentage from companies
    roce_query = "SELECT id as company_id, roce_percentage FROM companies"
    roce_df = pd.read_sql(roce_query, conn)
    roce_map = dict(zip(roce_df['company_id'], roce_df['roce_percentage']))
    df['roce_percentage'] = df['company_id'].map(roce_map).fillna(0.0)
    
    # Fill remaining NaNs for clustering safety
    df['return_on_equity_pct'] = df['return_on_equity_pct'].fillna(df['return_on_equity_pct'].median())
    df['debt_to_equity'] = df['debt_to_equity'].fillna(0.0)
    df['sales_cagr_5yr'] = df['sales_cagr_5yr'].fillna(0.0)
    df['fcf_cagr_5yr'] = df['fcf_cagr_5yr'].fillna(0.0)
    df['operating_profit_margin_pct'] = df['operating_profit_margin_pct'].fillna(df['operating_profit_margin_pct'].median())
    df['asset_turnover'] = df['asset_turnover'].fillna(df['asset_turnover'].median())
    df['roce_percentage'] = df['roce_percentage'].fillna(df['roce_percentage'].median())
    
    # Features for KMeans
    features = ['return_on_equity_pct', 'debt_to_equity', 'sales_cagr_5yr', 'fcf_cagr_5yr', 'operating_profit_margin_pct']
    X = df[features].copy()
    
    # Standardise
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # KMeans Clustering (K = 5)
    kmeans = KMeans(n_clusters=5, random_state=42, n_init=10)
    df['cluster_id'] = kmeans.fit_predict(X_scaled)
    
    # Analyze centroids to assign names
    centroids = kmeans.cluster_centers_
    # Let's map back centroids to original scale for interpretation
    centroids_orig = scaler.inverse_transform(centroids)
    
    cluster_profiles = {}
    for i in range(5):
        c_orig = centroids_orig[i]
        roe, de, sales_cagr, fcf_cagr, opm = c_orig
        
        # Simple heuristic to name the clusters
        if de > 1.2:
            name = "Leveraged / High Debt"
            desc = "Companies with high debt-to-equity ratio and lower operational performance."
        elif roe > 18.0 and sales_cagr > 12.0:
            name = "High-Quality Growth Compounder"
            desc = "Premium companies with superior return on equity and strong revenue growth."
        elif opm > 22.0 and de < 0.5:
            name = "Sturdy Cash Cows"
            desc = "Highly profitable, asset-light companies with stable cash generation and low debt."
        elif roe < 8.0 or sales_cagr < 5.0:
            name = "Underperformers / Cyclical Lows"
            desc = "Companies experiencing muted earnings, low growth, or cyclical headwinds."
        else:
            name = "Steady Performers"
            desc = "Moderate returns, reasonable growth, and standard leverage profiles."
            
        cluster_profiles[i] = {"name": name, "description": desc}
    
    # Ensure all names are unique. If there are collisions, append IDs
    names_used = []
    final_profiles = {}
    for i, profile in cluster_profiles.items():
        name = profile["name"]
        if name in names_used:
            if name == "Steady Performers":
                name = "Market Averages"
            else:
                name = f"{name} (Group {i+1})"
        names_used.append(name)
        final_profiles[i] = {"name": name, "description": profile["description"]}
        
    df['cluster_name'] = df['cluster_id'].map(lambda cid: final_profiles[cid]['name'])
    df['cluster_description'] = df['cluster_id'].map(lambda cid: final_profiles[cid]['description'])
    
    # Save clusters back to SQLite database
    logger.info("Saving clusters to database...")
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS company_clusters")
    cursor.execute("""
    CREATE TABLE company_clusters (
        company_id VARCHAR(12) PRIMARY KEY,
        cluster_id INTEGER,
        cluster_name VARCHAR(100),
        cluster_description TEXT,
        FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE
    )
    """)
    conn.commit()
    
    cluster_records = df[['company_id', 'cluster_id', 'cluster_name', 'cluster_description']].values.tolist()
    cursor.executemany("""
    INSERT INTO company_clusters (company_id, cluster_id, cluster_name, cluster_description)
    VALUES (?, ?, ?, ?)
    """, cluster_records)
    conn.commit()
    
    # Export full clustering results to CSV
    os.makedirs("output", exist_ok=True)
    df.to_csv("output/clustering_results.csv", index=False)
    
    # 2. Pearson Correlation Matrix (10 core KPIs)
    kpis_10 = [
        'return_on_equity_pct', 'roce_percentage', 'net_profit_margin_pct', 'operating_profit_margin_pct',
        'debt_to_equity', 'interest_coverage', 'asset_turnover', 'free_cash_flow_cr',
        'sales_cagr_5yr', 'pat_cagr_5yr'
    ]
    
    # Ensure interest coverage is clean (handling 999/debt free)
    corr_df = df[kpis_10].copy()
    corr_df['interest_coverage'] = corr_df['interest_coverage'].replace(999.0, 50.0) # Cap for correlation calculation
    corr_matrix = corr_df.corr(method='pearson')
    corr_matrix.to_csv("output/correlation_matrix.csv")
    logger.info("Saved correlation matrix to output/correlation_matrix.csv")
    
    # 3. Sector Outlier Detection (Z-scores > 3.0)
    outliers = []
    for sector in df['sector'].unique():
        sec_df = df[df['sector'] == sector].copy()
        if len(sec_df) < 3:
            continue # Skip tiny sectors for z-score calculations
            
        for kpi in kpis_10:
            val = sec_df[kpi].fillna(0.0)
            mean = val.mean()
            std = val.std()
            if std == 0:
                continue
                
            z_scores = (val - mean) / std
            outlier_rows = sec_df[np.abs(z_scores) > 3.0]
            
            for idx, row in outlier_rows.iterrows():
                outliers.append({
                    'company_id': row['company_id'],
                    'company_name': row['company_name'],
                    'sector': sector,
                    'kpi': kpi,
                    'value': row[kpi],
                    'sector_mean': mean,
                    'z_score': z_scores.loc[idx]
                })
                
    outliers_df = pd.DataFrame(outliers)
    outliers_df.to_csv("output/sector_outliers.csv", index=False)
    logger.info(f"Saved {len(outliers_df)} sector outliers to output/sector_outliers.csv")
    
    # 4. Nifty 100 aggregate stats percentiles
    percentiles = [0.10, 0.25, 0.50, 0.75, 0.90]
    percentiles_dict = {}
    for kpi in kpis_10:
        cleaned_series = df[kpi].dropna()
        if kpi == 'interest_coverage':
            cleaned_series = cleaned_series.replace(999.0, np.nan).dropna()
        p_vals = cleaned_series.quantile(percentiles).tolist()
        percentiles_dict[kpi] = p_vals
        
    p_df = pd.DataFrame(percentiles_dict, index=['P10', 'P25', 'P50', 'P75', 'P90']).T
    p_df.to_csv("output/nifty100_percentiles.csv")
    logger.info("Saved percentiles summary to output/nifty100_percentiles.csv")
    
    conn.close()
    logger.info("Clustering and analytics completed successfully.")

if __name__ == "__main__":
    run_clustering_and_analytics()
