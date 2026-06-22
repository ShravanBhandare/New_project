import streamlit as st
import pandas as pd
import yaml
import os
from src.analytics.screener.engine import get_latest_screener_data, apply_preset_filters

st.set_page_config(layout="wide")

st.title("🔍 Multi-Criteria Investment Screener")

# Load Screener Config to get presets
CONFIG_PATH = "config/screener_config.yaml"
try:
    with open(CONFIG_PATH, 'r') as f:
        config = yaml.safe_load(f)
except Exception as e:
    config = {'presets': {}}

# Fetch Master Screener Data
@st.cache_data
def load_screener_base():
    return get_latest_screener_data()

df = load_screener_base()

# Sidebar: Preset Templates
st.sidebar.markdown("### Preset Investment Templates")
preset_options = ["None (Custom Sliders)"] + [k.replace('_', ' ').title() for k in config['presets'].keys()]
selected_preset_label = st.sidebar.selectbox("Choose a Preset template", preset_options)

# Helper to map label back to config key
preset_key = selected_preset_label.lower().replace(' ', '_')

# Default filter values
defaults = {
    'min_roe': 0.0,
    'max_de': 5.0,
    'min_fcf': -500.0,
    'min_rev_cagr': -50.0,
    'min_pat_cagr': -50.0,
    'max_pe': 100.0,
    'max_pb': 20.0,
    'min_div_yield': 0.0,
    'min_npm': -50.0,
    'min_roce': -50.0
}

# If a preset is chosen, pre-fill filters with its criteria
if preset_key in config['presets']:
    preset_filters = config['presets'][preset_key]['filters']
    for rule in preset_filters:
        metric = rule['metric']
        val = rule['value']
        op = rule['operator']
        
        if metric == 'return_on_equity_pct' and op == '>':
            defaults['min_roe'] = float(val)
        elif metric == 'debt_to_equity' and op == '<':
            defaults['max_de'] = float(val)
        elif metric == 'free_cash_flow_cr' and op == '>':
            defaults['min_fcf'] = float(val)
        elif metric == 'sales_cagr_5yr' and op == '>':
            defaults['min_rev_cagr'] = float(val)
        elif metric == 'pat_cagr_5yr' and op == '>':
            defaults['min_pat_cagr'] = float(val)
        elif metric == 'pe_ratio' and op == '<':
            defaults['max_pe'] = float(val)
        elif metric == 'pb_ratio' and op == '<':
            defaults['max_pb'] = float(val)
        elif metric == 'dividend_yield_pct' and op == '>':
            defaults['min_div_yield'] = float(val)
        elif metric == 'net_profit_margin_pct' and op == '>':
            defaults['min_npm'] = float(val)
        elif metric == 'roce_percentage' and op == '>':
            defaults['min_roce'] = float(val)

# Sidebar Sliders
st.sidebar.markdown("### Adjust Criteria Sliders")
min_roe = st.sidebar.slider("Minimum ROE (%)", -20.0, 60.0, defaults['min_roe'], 1.0)
max_de = st.sidebar.slider("Maximum Debt-to-Equity", 0.0, 5.0, defaults['max_de'], 0.1)
min_fcf = st.sidebar.slider("Minimum Free Cash Flow (Cr)", -1000.0, 5000.0, defaults['min_fcf'], 50.0)
min_rev_cagr = st.sidebar.slider("Minimum 5yr Revenue CAGR (%)", -30.0, 50.0, defaults['min_rev_cagr'], 1.0)
min_pat_cagr = st.sidebar.slider("Minimum 5yr PAT CAGR (%)", -30.0, 50.0, defaults['min_pat_cagr'], 1.0)
max_pe = st.sidebar.slider("Maximum P/E Ratio", 0.0, 80.0, defaults['max_pe'], 1.0)
max_pb = st.sidebar.slider("Maximum P/B Ratio", 0.0, 15.0, defaults['max_pb'], 0.5)
min_div_yield = st.sidebar.slider("Minimum Dividend Yield (%)", 0.0, 6.0, defaults['min_div_yield'], 0.1)
min_npm = st.sidebar.slider("Minimum Net Profit Margin (%)", -10.0, 40.0, defaults['min_npm'], 1.0)

# Filter logic
filtered_df = df[
    (df['return_on_equity_pct'] >= min_roe) &
    (df['debt_to_equity'] <= max_de) &
    (df['free_cash_flow_cr'] >= min_fcf) &
    (df['sales_cagr_5yr'] >= min_rev_cagr) &
    (df['pat_cagr_5yr'] >= min_pat_cagr) &
    (df['pe_ratio'].isna() | (df['pe_ratio'] <= max_pe)) &
    (df['pb_ratio'].isna() | (df['pb_ratio'] <= max_pb)) &
    (df['dividend_yield_pct'] >= min_div_yield) &
    (df['net_profit_margin_pct'] >= min_npm)
].copy()

# Sort by Composite Quality Score by default
filtered_df = filtered_df.sort_values(by='composite_score', ascending=False)

# Results view
st.subheader(f"Screening Results ({len(filtered_df)} matches)")

# Round values for display
display_df = filtered_df[[
    'company_id', 'company_name', 'sector', 'return_on_equity_pct', 'debt_to_equity',
    'free_cash_flow_cr', 'pe_ratio', 'dividend_yield_pct', 'sales_cagr_5yr',
    'pat_cagr_5yr', 'composite_score', 'fcf_yield'
]].copy()

for col in display_df.select_dtypes(include=['number']).columns:
    display_df[col] = display_df[col].round(2)

st.dataframe(display_df, use_container_width=True, height=500)

# Export buttons
col_dl1, col_dl2 = st.columns(2)
with col_dl1:
    csv = display_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Results as CSV",
        data=csv,
        file_name="screener_results.csv",
        mime="text/csv"
    )
