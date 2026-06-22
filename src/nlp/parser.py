import pandas as pd
import re
import os
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

RAW_DIR = "data/raw"

def parse_cagr_text(text: str) -> list:
    """
    Parse growth strings (e.g. '10 Years: 21%', '5 Years: 6%') using regex.
    Returns a list of tuples: (period_years, value_pct)
    """
    if not isinstance(text, str):
        return []
        
    pattern = r'(\d+)\s*Years?:?\s*([\d.-]+)%'
    matches = re.findall(pattern, text)
    
    parsed = []
    for m in matches:
        try:
            years = int(m[0])
            val = float(m[1])
            parsed.append((years, val))
        except ValueError:
            continue
    return parsed

def run_parser():
    logger.info("Running CAGR text parser...")
    analysis_path = os.path.join(RAW_DIR, "analysis.xlsx")
    if not os.path.exists(analysis_path):
        logger.error(f"Analysis file {analysis_path} not found.")
        return
        
    df = pd.read_excel(analysis_path, header=1)
    
    records = []
    columns_to_parse = {
        'compounded_sales_growth': 'Sales Growth',
        'compounded_profit_growth': 'Profit Growth',
        'stock_price_cagr': 'Stock Price CAGR',
        'roe': 'ROE'
    }
    
    for idx, row in df.iterrows():
        comp_id = str(row['company_id']).strip().upper()
        
        for col, metric_name in columns_to_parse.items():
            val_text = row.get(col)
            if pd.isna(val_text):
                continue
                
            parsed_list = parse_cagr_text(str(val_text))
            for years, pct in parsed_list:
                records.append({
                    'company_id': comp_id,
                    'metric_type': metric_name,
                    'period_years': years,
                    'value_pct': pct
                })
                
    out_df = pd.DataFrame(records)
    os.makedirs("output", exist_ok=True)
    out_path = "output/analysis_parsed.csv"
    out_df.to_csv(out_path, index=False)
    logger.info(f"Successfully parsed analysis CAGR text to {out_path} ({len(out_df)} rows).")

if __name__ == "__main__":
    run_parser()
