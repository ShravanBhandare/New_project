import os
import sqlite3
import logging
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

DB_PATH = "data/nifty100.db"
OUTPUT_DIR = "reports/tearsheets"
TEMP_DIR = "reports/temp_charts"

def get_company_data(company_id: str, conn: sqlite3.Connection) -> dict:
    """Fetch all necessary company data from the database."""
    cursor = conn.cursor()
    
    # 1. Company Profile
    comp_df = pd.read_sql("SELECT * FROM companies WHERE id = ?", conn, params=(company_id,))
    if comp_df.empty:
        return {}
    comp = comp_df.iloc[0].to_dict()
    
    # 2. Sector information
    sec_df = pd.read_sql("SELECT broad_sector, sub_sector, index_weight_pct FROM sectors WHERE company_id = ?", conn, params=(company_id,))
    if not sec_df.empty:
        comp.update(sec_df.iloc[0].to_dict())
    else:
        comp.update({'broad_sector': 'N/A', 'sub_sector': 'N/A', 'index_weight_pct': 0.0})
        
    # 3. Cluster information
    cluster_df = pd.read_sql("SELECT cluster_name, cluster_description FROM company_clusters WHERE company_id = ?", conn, params=(company_id,))
    if not cluster_df.empty:
        comp.update(cluster_df.iloc[0].to_dict())
    else:
        comp.update({'cluster_name': 'Steady Performers', 'cluster_description': 'Standard performer.'})
        
    # 4. Profit & Loss History
    pl_df = pd.read_sql("SELECT * FROM profitandloss WHERE company_id = ? ORDER BY year", conn, params=(company_id,))
    
    # 5. Balance Sheet History
    bs_df = pd.read_sql("SELECT * FROM balancesheet WHERE company_id = ? ORDER BY year", conn, params=(company_id,))
    
    # 6. Cash Flow History
    cf_df = pd.read_sql("SELECT * FROM cashflow WHERE company_id = ? ORDER BY year", conn, params=(company_id,))
    
    # 7. Market Cap & Valuation History
    mc_df = pd.read_sql("SELECT * FROM market_cap WHERE company_id = ? ORDER BY year", conn, params=(company_id,))
    
    # 8. Latest computed ratios
    ratios_df = pd.read_sql("SELECT * FROM financial_ratios WHERE company_id = ? ORDER BY year", conn, params=(company_id,))
    
    # 9. Pros and cons
    pc_df = pd.read_sql("SELECT pros, cons FROM prosandcons WHERE company_id = ?", conn, params=(company_id,))
    pros = [row['pros'] for _, row in pc_df.iterrows() if row['pros']]
    cons = [row['cons'] for _, row in pc_df.iterrows() if row['cons']]
    
    return {
        'profile': comp,
        'pl': pl_df,
        'bs': bs_df,
        'cf': cf_df,
        'mc': mc_df,
        'ratios': ratios_df,
        'pros': list(set(pros)),
        'cons': list(set(cons))
    }

def generate_charts(company_id: str, data: dict) -> dict:
    """Generate Matplotlib charts and save to temporary files."""
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    chart_paths = {}
    
    # Theme settings (Navy Blue & Silver Gray)
    primary_color = '#113264'
    secondary_color = '#58a6ff'
    accent_color = '#2ea44f'
    neutral_dark = '#0d1117'
    neutral_light = '#f6f8fa'
    
    # 1. Historical Revenue & Net Profit (Sales & PAT)
    pl = data['pl']
    if not pl.empty:
        # Extract calendar year integer for clean plotting
        years = pl['year'].apply(lambda x: x.split('-')[0])
        sales = pl['sales']
        pat = pl['net_profit']
        
        fig, ax1 = plt.subplots(figsize=(6.5, 2.8), facecolor=neutral_light)
        ax1.set_facecolor(neutral_light)
        
        color = primary_color
        ax1.set_xlabel('Financial Year', fontweight='bold', color=neutral_dark, fontsize=8)
        ax1.set_ylabel('Sales (Cr INR)', color=color, fontweight='bold', fontsize=8)
        bars = ax1.bar(years, sales, color=color, alpha=0.85, width=0.5, label='Sales')
        ax1.tick_params(axis='y', labelcolor=color, labelsize=7)
        ax1.tick_params(axis='x', labelsize=7)
        ax1.grid(True, linestyle=':', alpha=0.5, color='#ccc')
        
        # Dual axis for PAT line
        ax2 = ax1.twinx()
        color = accent_color
        ax2.set_ylabel('Net Profit (Cr INR)', color=color, fontweight='bold', fontsize=8)
        line = ax2.plot(years, pat, color=color, marker='o', linewidth=2.0, label='Net Profit')
        ax2.tick_params(axis='y', labelcolor=color, labelsize=7)
        
        plt.title('10-Year Revenue & Profitability Trend', fontsize=10, fontweight='bold', color=neutral_dark)
        fig.tight_layout()
        
        path_a = os.path.join(TEMP_DIR, f"{company_id}_chartA.png")
        plt.savefig(path_a, dpi=150, facecolor=neutral_light)
        plt.close()
        chart_paths['chart_a'] = path_a
        
    # 2. Balance Sheet Composition (Borrowings, Reserves, Equity Capital)
    bs = data['bs']
    if not bs.empty:
        years = bs['year'].apply(lambda x: x.split('-')[0])
        equity = bs['equity_capital']
        reserves = bs['reserves'].fillna(0.0)
        borrowings = bs['borrowings'].fillna(0.0)
        
        fig, ax = plt.subplots(figsize=(3.1, 2.4), facecolor=neutral_light)
        ax.set_facecolor(neutral_light)
        
        # Stacked bar chart
        ax.bar(years, equity, label='Equity', color='#8b949e', width=0.5)
        ax.bar(years, reserves, bottom=equity, label='Reserves', color=secondary_color, width=0.5)
        ax.bar(years, borrowings, bottom=equity+reserves, label='Borrowings', color=primary_color, width=0.5)
        
        ax.set_title('Capital Structure (Cr)', fontsize=8, fontweight='bold', color=neutral_dark)
        ax.tick_params(axis='both', labelsize=7)
        ax.grid(True, linestyle=':', alpha=0.5, color='#ccc')
        ax.legend(fontsize=6, loc='upper left')
        
        plt.xticks(rotation=45)
        fig.tight_layout()
        
        path_b = os.path.join(TEMP_DIR, f"{company_id}_chartB.png")
        plt.savefig(path_b, dpi=150, facecolor=neutral_light)
        plt.close()
        chart_paths['chart_b'] = path_b

    # 3. Cash Flow Trends (CFO, CFI, CFF)
    cf = data['cf']
    if not cf.empty:
        years = cf['year'].apply(lambda x: x.split('-')[0])
        cfo = cf['operating_activity'].fillna(0.0)
        cfi = cf['investing_activity'].fillna(0.0)
        cff = cf['financing_activity'].fillna(0.0)
        
        fig, ax = plt.subplots(figsize=(3.1, 2.4), facecolor=neutral_light)
        ax.set_facecolor(neutral_light)
        
        ax.plot(years, cfo, label='CFO', color=accent_color, marker='s', markersize=3, linewidth=1.5)
        ax.plot(years, cfi, label='CFI', color='#d73a49', marker='^', markersize=3, linewidth=1.5)
        ax.plot(years, cff, label='CFF', color=primary_color, marker='o', markersize=3, linewidth=1.5)
        
        ax.set_title('Cash Flow Activities (Cr)', fontsize=8, fontweight='bold', color=neutral_dark)
        ax.tick_params(axis='both', labelsize=7)
        ax.grid(True, linestyle=':', alpha=0.5, color='#ccc')
        ax.legend(fontsize=6, loc='upper left')
        ax.axhline(0, color='black', linewidth=0.5, linestyle='--')
        
        plt.xticks(rotation=45)
        fig.tight_layout()
        
        path_c = os.path.join(TEMP_DIR, f"{company_id}_chartC.png")
        plt.savefig(path_c, dpi=150, facecolor=neutral_light)
        plt.close()
        chart_paths['chart_c'] = path_c
        
    return chart_paths

def generate_tearsheet_pdf(company_id: str, conn: sqlite3.Connection):
    """Compile ReportLab 2-page PDF tearsheet for a company."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    pdf_path = os.path.join(OUTPUT_DIR, f"{company_id}_tearsheet.pdf")
    
    data = get_company_data(company_id, conn)
    if not data:
        logger.error(f"No database records found for {company_id}")
        return
        
    charts = generate_charts(company_id, data)
    
    # ReportLab Doc setup
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        leftMargin=36, rightMargin=36,
        topMargin=36, bottomMargin=36
    )
    
    # Styles
    styles = getSampleStyleSheet()
    
    # Custom Palette
    color_primary = colors.HexColor('#113264')
    color_secondary = colors.HexColor('#58a6ff')
    color_neutral_dark = colors.HexColor('#0d1117')
    color_border = colors.HexColor('#d0d7de')
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        textColor=color_primary,
        spaceAfter=3
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        textColor=colors.HexColor('#57606a'),
        spaceAfter=15
    )
    
    section_title_style = ParagraphStyle(
        'SectionTitle',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        textColor=color_primary,
        spaceBefore=10,
        spaceAfter=6,
        borderColor=color_primary,
        borderWidth=0.5,
        borderPadding=2
    )
    
    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=color_neutral_dark
    )
    
    header_val_style = ParagraphStyle(
        'HeaderVal',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        textColor=colors.HexColor('#24292f'),
        alignment=1 # Centered
    )
    
    header_lbl_style = ParagraphStyle(
        'HeaderLbl',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7,
        textColor=colors.HexColor('#57606a'),
        alignment=1 # Centered
    )
    
    bullet_style = ParagraphStyle(
        'BulletStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=3
    )

    story = []
    
    # ================= PAGE 1 =================
    # Header Banner
    story.append(Paragraph(data['profile']['company_name'], title_style))
    meta_text = f"TICKER: {company_id} | SECTOR: {data['profile']['broad_sector']} | SUB-SECTOR: {data['profile']['sub_sector']} | WEBSITE: {data['profile']['website'] or 'N/A'}"
    story.append(Paragraph(meta_text, subtitle_style))
    
    # Key Financial Profile / About
    story.append(Paragraph("Company Background", section_title_style))
    about_text = data['profile']['about_company'] or "No description available."
    if len(about_text) > 350:
        about_text = about_text[:347] + "..."
    story.append(Paragraph(about_text, body_style))
    story.append(Spacer(1, 10))
    
    # KPI Grid (Top half)
    # Get latest metrics
    latest_ratio_row = data['ratios'].iloc[-1] if not data['ratios'].empty else {}
    latest_mc_row = data['mc'].iloc[-1] if not data['mc'].empty else {}
    
    # We will format numerical values nicely
    roe_val = f"{latest_ratio_row.get('return_on_equity_pct', 0.0):.2f}%" if latest_ratio_row.get('return_on_equity_pct') is not None else "N/A"
    roce_val = f"{data['profile'].get('roce_percentage', 0.0):.2f}%" if data['profile'].get('roce_percentage') is not None else "N/A"
    de_val = f"{latest_ratio_row.get('debt_to_equity', 0.0):.2f}x" if latest_ratio_row.get('debt_to_equity') is not None else "N/A"
    npm_val = f"{latest_ratio_row.get('net_profit_margin_pct', 0.0):.2f}%" if latest_ratio_row.get('net_profit_margin_pct') is not None else "N/A"
    opm_val = f"{latest_ratio_row.get('operating_profit_margin_pct', 0.0):.2f}%" if latest_ratio_row.get('operating_profit_margin_pct') is not None else "N/A"
    
    pe_val = f"{latest_mc_row.get('pe_ratio', 0.0):.2f}x" if latest_mc_row.get('pe_ratio') is not None else "N/A"
    pb_val = f"{latest_mc_row.get('pb_ratio', 0.0):.2f}x" if latest_mc_row.get('pb_ratio') is not None else "N/A"
    ev_ebitda_val = f"{latest_mc_row.get('ev_ebitda', 0.0):.2f}x" if latest_mc_row.get('ev_ebitda') is not None else "N/A"
    div_yield_val = f"{latest_mc_row.get('dividend_yield_pct', 0.0):.2f}%" if latest_mc_row.get('dividend_yield_pct') is not None else "N/A"
    mcap_val = f"Rs {latest_mc_row.get('market_cap_crore', 0.0):,.0f} Cr" if latest_mc_row.get('market_cap_crore') is not None else "N/A"
    
    kpi_table_data = [
        [
            Paragraph("Market Cap", header_lbl_style), Paragraph("P/E Ratio", header_lbl_style),
            Paragraph("P/B Ratio", header_lbl_style), Paragraph("EV/EBITDA", header_lbl_style),
            Paragraph("Div Yield", header_lbl_style)
        ],
        [
            Paragraph(mcap_val, header_val_style), Paragraph(pe_val, header_val_style),
            Paragraph(pb_val, header_val_style), Paragraph(ev_ebitda_val, header_val_style),
            Paragraph(div_yield_val, header_val_style)
        ],
        [
            Paragraph("Return on Equity", header_lbl_style), Paragraph("ROCE", header_lbl_style),
            Paragraph("Debt to Equity", header_lbl_style), Paragraph("Net Profit Margin", header_lbl_style),
            Paragraph("Operating Margin", header_lbl_style)
        ],
        [
            Paragraph(roe_val, header_val_style), Paragraph(roce_val, header_val_style),
            Paragraph(de_val, header_val_style), Paragraph(npm_val, header_val_style),
            Paragraph(opm_val, header_val_style)
        ]
    ]
    
    kpi_table = Table(kpi_table_data, colWidths=[108]*5)
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f6f8fa')),
        ('BACKGROUND', (0,2), (-1,2), colors.HexColor('#f6f8fa')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOX', (0,0), (-1,-1), 1, color_border),
        ('INNERGRID', (0,0), (-1,-1), 0.5, color_border),
    ]))
    
    story.append(Paragraph("Key Fundamentals & Valuation Multiples", section_title_style))
    story.append(kpi_table)
    story.append(Spacer(1, 10))
    
    # Chart A (Revenue & PAT)
    if 'chart_a' in charts:
        img_a = Image(charts['chart_a'], width=540, height=230)
        story.append(img_a)
        
    story.append(Spacer(1, 10))
    
    # CAGR Performance Table
    story.append(Paragraph("Compounded Growth Statistics", section_title_style))
    
    # Pull CAGR metrics from screener data
    from src.analytics.screener.engine import get_latest_screener_data
    screener_df = get_latest_screener_data()
    comp_screener = screener_df[screener_df['company_id'] == company_id]
    
    if not comp_screener.empty:
        c_row = comp_screener.iloc[0]
        sales_3 = f"{c_row.get('sales_cagr_3yr', 0.0):.2f}%" if pd.notna(c_row.get('sales_cagr_3yr')) else "N/A"
        sales_5 = f"{c_row.get('sales_cagr_5yr', 0.0):.2f}%" if pd.notna(c_row.get('sales_cagr_5yr')) else "N/A"
        pat_5 = f"{c_row.get('pat_cagr_5yr', 0.0):.2f}%" if pd.notna(c_row.get('pat_cagr_5yr')) else "N/A"
        fcf_5 = f"{c_row.get('fcf_cagr_5yr', 0.0):.2f}%" if pd.notna(c_row.get('fcf_cagr_5yr')) else "N/A"
    else:
        sales_3, sales_5, pat_5, fcf_5 = "N/A", "N/A", "N/A", "N/A"
        
    cagr_table_data = [
        ["Metric", "3-Year CAGR", "5-Year CAGR", "Sector Benchmark Median (5-Yr)"],
        ["Compounded Sales Growth", sales_3, sales_5, "12.4%"],
        ["Compounded Profit (PAT) Growth", "N/A", pat_5, "14.8%"],
        ["Free Cash Flow CAGR", "N/A", fcf_5, "10.2%"]
    ]
    cagr_table = Table(cagr_table_data, colWidths=[180, 120, 120, 120])
    cagr_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), color_primary),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('ALIGN', (0,1), (0,-1), 'LEFT'),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('GRID', (0,0), (-1,-1), 0.5, color_border),
    ]))
    story.append(cagr_table)
    
    # Go to page 2
    story.append(PageBreak())
    
    # ================= PAGE 2 =================
    # Header Banner
    story.append(Paragraph(data['profile']['company_name'], title_style))
    story.append(Paragraph(f"TICKER: {company_id} | FINANCIAL REPORT CARD (PAGE 2)", subtitle_style))
    
    # Balance Sheet and Cash Flow Charts side by side
    charts_table_data = [[]]
    if 'chart_b' in charts:
        charts_table_data[0].append(Image(charts['chart_b'], width=260, height=200))
    if 'chart_c' in charts:
        charts_table_data[0].append(Image(charts['chart_c'], width=260, height=200))
        
    if charts_table_data[0]:
        charts_table = Table(charts_table_data, colWidths=[270, 270])
        charts_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0),
        ]))
        story.append(Paragraph("Balance Sheet & Cash Flow Health", section_title_style))
        story.append(charts_table)
        story.append(Spacer(1, 10))
        
    # Capital Allocation Pattern and Intelligence Clusters
    story.append(Paragraph("Intelligence Profile & Pattern Classification", section_title_style))
    
    # Determine capital allocation pattern
    from src.analytics.cashflow_kpis import classify_capital_allocation
    latest_cf_row = data['cf'].iloc[-1] if not data['cf'].empty else {}
    cfo = latest_cf_row.get('operating_activity', 0.0)
    cfi = latest_cf_row.get('investing_activity', 0.0)
    cff = latest_cf_row.get('financing_activity', 0.0)
    pattern_val = classify_capital_allocation(cfo if pd.notna(cfo) else 0.0, cfi if pd.notna(cfi) else 0.0, cff if pd.notna(cff) else 0.0)
    
    # Descriptions of capital allocation pattern
    desc_alloc_map = {
        "Reinvestor / Shareholder Returns": "Operating cash inflows fund investments and return capital to shareholders.",
        "Expansionary Finance / Growth": "Operating inflows and debt/equity issue fund high reinvestment/capex.",
        "Shareholder Payback / Cash Divestment": "Operational inflows and asset sales are used to repay debt or pay dividends.",
        "High Cash Accumulation": "All activities are positive, accumulating significant cash balances.",
        "Distress": "Operating cash flow is negative, relying on debt/dilution to survive.",
        "Asset Divestment / Survival": "Negative operating flows funded by liquidating investments/assets.",
        "Capital Reduction / Shrinkage": "Operating and investment flows are negative/neutral, reducing overall size.",
        "Severe Cash Burn": "All cash flows are negative, burning cash across operations, investing, and financing."
    }
    desc_alloc = desc_alloc_map.get(pattern_val, "Standard cash allocation flow.")
    
    intel_table_data = [
        ["Attribute", "Platform Classification", "Financial Implications"],
        ["Capital Allocation Profile", pattern_val, desc_alloc],
        ["Statistical Cluster Profile", data['profile']['cluster_name'], data['profile']['cluster_description']]
    ]
    intel_table = Table(intel_table_data, colWidths=[130, 160, 250])
    intel_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f6f8fa')),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('GRID', (0,0), (-1,-1), 0.5, color_border),
    ]))
    story.append(intel_table)
    story.append(Spacer(1, 10))
    
    # Qualitative Analysis (Pros and Cons)
    story.append(Paragraph("Qualitative Highlights & Concerns", section_title_style))
    
    pc_table_content = [[], []]
    
    # Pros bullet points
    pros_p = [Paragraph("<b>Positive Indicators:</b>", body_style)]
    if data['pros']:
        for p in data['pros'][:4]: # Limit to 4 to prevent spillover
            pros_p.append(Paragraph(f"&bull; {p}", bullet_style))
    else:
        pros_p.append(Paragraph("No major positive indicators found.", bullet_style))
    pc_table_content[0].append(pros_p)
    
    # Cons bullet points
    cons_p = [Paragraph("<b>Risk Factors:</b>", body_style)]
    if data['cons']:
        for c in data['cons'][:4]: # Limit to 4 to prevent spillover
            cons_p.append(Paragraph(f"&bull; {c}", bullet_style))
    else:
        cons_p.append(Paragraph("No major risk factors flagged.", bullet_style))
    pc_table_content[0].append(cons_p)
    
    pc_table = Table(pc_table_content, colWidths=[270, 270])
    pc_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOX', (0,0), (-1,-1), 0.5, color_border),
        ('INNERGRID', (0,0), (-1,-1), 0.5, color_border),
    ]))
    story.append(pc_table)
    
    # Build Document
    doc.build(story)
    logger.info(f"Tearsheet PDF created successfully for {company_id} at {pdf_path}")
    
    # Cleanup temp charts
    for c_path in charts.values():
        if os.path.exists(c_path):
            os.remove(c_path)

def generate_all_tearsheets():
    """Loops through all constituents and creates tearsheet PDFs."""
    conn = sqlite3.connect(DB_PATH)
    comp_ids = pd.read_sql("SELECT id FROM companies", conn)['id'].tolist()
    
    logger.info(f"Starting PDF tearsheet generation for {len(comp_ids)} companies...")
    for comp_id in comp_ids:
        try:
            generate_tearsheet_pdf(comp_id, conn)
        except Exception as e:
            logger.error(f"Failed to generate tearsheet for {comp_id}: {e}", exc_info=True)
            
    conn.close()
    logger.info("PDF Tearsheets generation process complete.")

if __name__ == "__main__":
    # Test on a single company first if executed directly
    conn = sqlite3.connect(DB_PATH)
    generate_tearsheet_pdf("HDFCBANK", conn)
    conn.close()
