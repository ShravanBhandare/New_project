import os
import sqlite3
import pandas as pd
import logging
from nltk.sentiment.vader import SentimentIntensityAnalyzer

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

DB_PATH = "data/nifty100.db"

def run_pros_cons_generator():
    logger.info("Initializing NLTK VADER sentiment analyzer...")
    # Initialize VADER
    try:
        sid = SentimentIntensityAnalyzer()
    except Exception as e:
        logger.error(f"Failed to initialize VADER: {e}. Downloading nltk data first.")
        import nltk
        nltk.download('vader_lexicon', quiet=True)
        sid = SentimentIntensityAnalyzer()
        
    logger.info("Connecting to database to fetch company metrics...")
    conn = sqlite3.connect(DB_PATH)
    
    # We will fetch latest data from get_latest_screener_data logic or query financial_ratios and market_cap directly
    # Since we already have the get_latest_screener_data function, let's reuse it or fetch directly
    from src.analytics.peer import get_peer_comparison_data
    df = get_peer_comparison_data()
    
    records = []
    
    for idx, row in df.iterrows():
        comp_id = row['company_id']
        roe = row['return_on_equity_pct']
        roce = row['roce_percentage']
        npm = row['net_profit_margin_pct']
        de = row['debt_to_equity']
        icr = row['interest_coverage']
        fcf = row['free_cash_flow_cr']
        sales = row['sales']
        net_profit = row['net_profit']
        sales_cagr = row['sales_cagr_5yr']
        pat_cagr = row['pat_cagr_5yr']
        fcf_cagr = row['fcf_cagr_5yr']
        cfo_pat = row['cfo_pat_ratio']
        pe = row['pe_ratio']
        pb = row['pb_ratio']
        div_yield = row['dividend_yield_pct']
        div_payout = row['dividend_payout_ratio_pct']
        
        # 12 PRO RULES
        pro_rules = [
            (roe > 20.0, "ROE > 20%", f"Company has shown robust return on equity (ROE of {roe:.1f}%) indicating highly profitable usage of shareholder funds."),
            (fcf > 100.0, "FCF > 100 Cr", f"Strong positive free cash flow generation of {fcf:.1f} Cr indicating excellent liquidity."),
            (de == 0.0, "Debt-Free", "Virtually debt-free balance sheet, reducing leverage risk."),
            (sales_cagr > 15.0, "Sales CAGR 5yr > 15%", f"Excellent 5-year revenue growth trajectory with a CAGR of {sales_cagr:.1f}%."),
            (pat_cagr > 15.0, "PAT CAGR 5yr > 15%", f"Strong net profit expansion over the last 5 years (CAGR of {pat_cagr:.1f}%)."),
            (icr > 5.0, "ICR > 5.0", f"High interest coverage ratio of {icr:.1f}x, easily meeting debt obligations."),
            (cfo_pat > 1.0, "CFO/PAT > 1.0", f"High quality of earnings with operating cash flow exceeding net profit (CFO/PAT = {cfo_pat:.2f})."),
            (npm > 25.0, "NPM > 25%", f"Outstanding net profitability margin of {npm:.1f}%."),
            (div_yield > 2.0, "Dividend Yield > 2%", f"Attractive dividend yield of {div_yield:.1f}% providing consistent cash returns."),
            (fcf_cagr > 10.0, "FCF CAGR 5yr > 10%", f"Efficient multi-year FCF compound growth of {fcf_cagr:.1f}%."),
            (pe is not None and 0 < pe < 15.0, "P/E < 15.0", f"Trading at an attractive valuation multiple with a P/E of {pe:.1f}x."),
            (roce > 20.0, "ROCE > 20%", f"Solid return on capital employed (ROCE of {roce:.1f}%) demonstrating strong operational efficiency.")
        ]
        
        # 12 CON RULES
        con_rules = [
            (roe < 10.0, "ROE < 10%", f"Sub-optimal return on equity (ROE of {roe:.1f}%) indicating low capital efficiency."),
            (fcf < 0.0, "FCF < 0", f"Negative free cash flow generation of {fcf:.1f} Cr, suggesting cash drain."),
            (de > 2.0, "D/E > 2.0", f"Highly leveraged balance sheet with debt-to-equity ratio of {de:.2f}x."),
            (sales_cagr < 5.0, "Sales CAGR 5yr < 5%", f"Stagnant or low sales growth over the last 5 years (CAGR of {sales_cagr:.1f}%)."),
            (pat_cagr < 0.0, "PAT CAGR 5yr < 0%", f"Decline in net profit over the last 5 years with a negative CAGR of {pat_cagr:.1f}%."),
            (icr is not None and icr < 1.5, "ICR < 1.5", f"Weak interest coverage ratio of {icr:.1f}x showing high debt servicing risk."),
            (cfo_pat < 0.5, "CFO/PAT < 0.5", f"Low earnings quality with operating cash flows significantly below net profit (CFO/PAT = {cfo_pat:.2f})."),
            (npm < 8.0, "NPM < 8%", f"Thin net margins of {npm:.1f}%, vulnerable to cost spikes."),
            (pe is not None and pe > 50.0, "P/E > 50.0", f"Rich valuation multiple, trading at a very high P/E ratio of {pe:.1f}x."),
            (pb is not None and pb > 8.0, "P/B > 8.0", f"High price-to-book valuation multiple of {pb:.1f}x."),
            (fcf_cagr < 0.0, "FCF CAGR 5yr < 0%", f"Decline in free cash flow generation over 5 years (CAGR of {fcf_cagr:.1f}%)."),
            (div_payout > 100.0, "Dividend Payout > 100%", f"Dividend payout ratio of {div_payout:.1f}% exceeds net profit, which may be unsustainable.")
        ]
        
        has_pro = False
        has_con = False
        
        # Evaluate pros
        for cond, rule_id, text in pro_rules:
            if cond:
                has_pro = True
                scores = sid.polarity_scores(text)
                confidence = abs(scores['compound']) * 100.0 if scores['compound'] != 0 else 90.0
                records.append({
                    'company_id': comp_id,
                    'type': 'pro',
                    'rule_triggered': rule_id,
                    'text': text,
                    'confidence_pct': round(max(confidence, 60.0), 2)
                })
                
        # Evaluate cons
        for cond, rule_id, text in con_rules:
            if cond:
                has_con = True
                scores = sid.polarity_scores(text)
                confidence = abs(scores['compound']) * 100.0 if scores['compound'] != 0 else 90.0
                records.append({
                    'company_id': comp_id,
                    'type': 'con',
                    'rule_triggered': rule_id,
                    'text': text,
                    'confidence_pct': round(max(confidence, 60.0), 2)
                })
                
        # If no pro triggers, add default neutral pro
        if not has_pro:
            text = "Consistent operations in line with standard industry multiples."
            records.append({
                'company_id': comp_id,
                'type': 'pro',
                'rule_triggered': 'DEFAULT',
                'text': text,
                'confidence_pct': 70.0
            })
            
        # If no con triggers, add default neutral con
        if not has_con:
            text = "Potential vulnerability to macro-economic changes and sector-specific rotation."
            records.append({
                'company_id': comp_id,
                'type': 'con',
                'rule_triggered': 'DEFAULT',
                'text': text,
                'confidence_pct': 70.0
            })
            
    conn.close()
    
    out_df = pd.DataFrame(records)
    os.makedirs("output", exist_ok=True)
    out_path = "output/pros_cons_generated.csv"
    out_df.to_csv(out_path, index=False)
    logger.info(f"Successfully generated pros and cons CSV to {out_path} ({len(out_df)} records).")

if __name__ == "__main__":
    run_pros_cons_generator()
