import os
import sqlite3
import logging
import pandas as pd
import numpy as np

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

DB_PATH = "data/nifty100.db"
OUTPUT_DIR = "reports"

def get_portfolio_data(conn: sqlite3.Connection) -> dict:
    """Load master list of all 92 constituents with their primary analytics."""
    query = """
    SELECT 
        s.company_id, c.company_name, s.broad_sector, s.sub_sector, s.index_weight_pct,
        r.return_on_equity_pct, r.debt_to_equity, r.net_profit_margin_pct,
        mc.market_cap_crore, mc.pe_ratio, mc.dividend_yield_pct
    FROM sectors s
    JOIN companies c ON s.company_id = c.id
    LEFT JOIN financial_ratios r ON s.company_id = r.company_id AND r.year = (
        SELECT MAX(year) FROM financial_ratios WHERE company_id = s.company_id
    )
    LEFT JOIN market_cap mc ON s.company_id = mc.company_id AND mc.year = 2024
    """
    df = pd.read_sql(query, conn)
    
    # Merge with CAGR and Composite Score from screener data
    from src.analytics.screener.engine import get_latest_screener_data
    screener_df = get_latest_screener_data()
    cagr_subset = screener_df[['company_id', 'sales_cagr_5yr', 'pat_cagr_5yr', 'composite_score']].copy()
    
    df = df.merge(cagr_subset, on='company_id', how='left')
    
    # Aggregate statistics
    total_mcap = df['market_cap_crore'].sum()
    median_pe = df['pe_ratio'].median()
    avg_roe = df['return_on_equity_pct'].mean()
    median_de = df['debt_to_equity'].median()
    
    # Sector distributions
    sector_summary = df.groupby('broad_sector').agg(
        weight=('index_weight_pct', 'sum'),
        companies_count=('company_id', 'count'),
        mcap=('market_cap_crore', 'sum')
    ).reset_index()
    
    # Sort sector summary by weight descending
    sector_summary = sector_summary.sort_values(by='weight', ascending=False)
    
    return {
        'total_mcap': total_mcap,
        'median_pe': median_pe,
        'avg_roe': avg_roe,
        'median_de': median_de,
        'constituents': df.to_dict(orient='records'),
        'sector_summary': sector_summary.to_dict(orient='records')
    }

def generate_portfolio_pdf():
    """Generates the main index-level Portfolio Report PDF."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    pdf_path = os.path.join(OUTPUT_DIR, "nifty100_portfolio_report.pdf")
    
    conn = sqlite3.connect(DB_PATH)
    data = get_portfolio_data(conn)
    conn.close()
    
    # Doc template
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        leftMargin=36, rightMargin=36,
        topMargin=36, bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    
    # Themes
    color_primary = colors.HexColor('#113264')
    color_secondary = colors.HexColor('#58a6ff')
    color_border = colors.HexColor('#d0d7de')
    
    title_style = ParagraphStyle(
        'PortTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=22,
        textColor=color_primary,
        spaceAfter=5
    )
    
    subtitle_style = ParagraphStyle(
        'PortSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        textColor=colors.HexColor('#57606a'),
        spaceAfter=20
    )
    
    section_title_style = ParagraphStyle(
        'PortSecTitle',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=13,
        textColor=color_primary,
        spaceBefore=14,
        spaceAfter=8,
        borderColor=color_primary,
        borderWidth=0.5,
        borderPadding=2
    )
    
    body_style = ParagraphStyle(
        'PortBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor('#0d1117')
    )
    
    table_hdr_style = ParagraphStyle(
        'PortTableHdr',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7,
        textColor=colors.white,
        alignment=1
    )
    
    table_cell_style = ParagraphStyle(
        'PortTableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7,
        textColor=colors.HexColor('#24292f'),
        alignment=1
    )
    
    table_cell_left_style = ParagraphStyle(
        'PortTableCellLeft',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7,
        textColor=colors.HexColor('#24292f'),
        alignment=0
    )

    story = []
    
    # ================= PAGE 1 =================
    story.append(Paragraph("Nifty 100 Index Portfolio Intelligence Report", title_style))
    meta_text = f"PORTFOLIO AGGREGATE DASHBOARD | CONSTITUENTS: 92 | DATE: June 2026"
    story.append(Paragraph(meta_text, subtitle_style))
    
    # Index Executive Summary
    story.append(Paragraph("Executive Summary", section_title_style))
    exec_text = (
        "This intelligence report compiles and aggregates fundamental metrics across all 92 constituent "
        "companies of the Nifty 100 platform. The index represents the largest companies listed on the "
        "National Stock Exchange (NSE) in India. By standardizing financials over a 10-year period, this "
        "report details aggregate valuation metrics, sector allocations, and constituent rank details "
        "to assist institutional allocators with systematic fundamentals tracking."
    )
    story.append(Paragraph(exec_text, body_style))
    story.append(Spacer(1, 10))
    
    # Aggregate Stats Table
    story.append(Paragraph("Index Aggregates Summary", section_title_style))
    stats_data = [
        ["Aggregate Metric", "Value", "Benchmark Target Interpretation"],
        ["Total Portfolio Market Cap", f"Rs {data['total_mcap']:,.0f} Cr", "Sum of all active company valuations"],
        ["Median Valuation P/E Ratio", f"{data['median_pe']:.1f}x", "Aggregate price-to-earnings multiple"],
        ["Average Return on Equity (ROE)", f"{data['avg_roe']:.1f}%", "Unweighted average return on equity"],
        ["Median Debt-to-Equity Ratio", f"{data['median_de']:.2f}x", "Median financial leverage ratio"]
    ]
    stats_table = Table(stats_data, colWidths=[180, 140, 220])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f6f8fa')),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('FONTSIZE', (0,1), (-1,-1), 9),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('GRID', (0,0), (-1,-1), 0.5, color_border),
    ]))
    story.append(stats_table)
    story.append(Spacer(1, 10))
    
    # Sector Allocation
    story.append(Paragraph("Sector Allocation Breakdown", section_title_style))
    sec_data = [["Broad Sector Name", "Constituents Count", "Market Capitalization (Cr)", "Cumulative Index Weight"]]
    for s in data['sector_summary']:
        sec_data.append([
            s['broad_sector'],
            str(s['companies_count']),
            f"Rs {s['mcap']:,.0f}",
            f"{s['weight']:.2f}%" if pd.notna(s['weight']) else "0.00%"
        ])
    sec_table = Table(sec_data, colWidths=[180, 100, 140, 120])
    sec_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), color_primary),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('ALIGN', (0,1), (0,-1), 'LEFT'),
        ('FONTSIZE', (0,1), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('GRID', (0,0), (-1,-1), 0.5, color_border),
    ]))
    story.append(sec_table)
    
    story.append(PageBreak())
    
    # ================= PAGE 2 onwards: Master Table =================
    story.append(Paragraph("Master Index Constituents Reference List", section_title_style))
    
    # Table header
    hdr_row = [
        Paragraph("Ticker", table_hdr_style),
        Paragraph("Company Name", table_hdr_style),
        Paragraph("Broad Sector", table_hdr_style),
        Paragraph("Weight %", table_hdr_style),
        Paragraph("Market Cap (Cr)", table_hdr_style),
        Paragraph("P/E", table_hdr_style),
        Paragraph("ROE %", table_hdr_style),
        Paragraph("D/E Ratio", table_hdr_style),
        Paragraph("Sales CAGR (5Yr)", table_hdr_style),
        Paragraph("Score", table_hdr_style)
    ]
    
    master_table_data = [hdr_row]
    
    # Sort constituents by index weight descending
    constituents = sorted(data['constituents'], key=lambda x: x['index_weight_pct'] if pd.notna(x['index_weight_pct']) else 0.0, reverse=True)
    
    for c in constituents:
        weight_f = f"{c.get('index_weight_pct', 0.0):.2f}%" if pd.notna(c.get('index_weight_pct')) else "0.00%"
        mcap_f = f"{c.get('market_cap_crore', 0.0):,.0f}" if pd.notna(c.get('market_cap_crore')) else "N/A"
        pe_f = f"{c.get('pe_ratio', 0.0):.1f}x" if pd.notna(c.get('pe_ratio')) else "N/A"
        roe_f = f"{c.get('return_on_equity_pct', 0.0):.1f}%" if pd.notna(c.get('return_on_equity_pct')) else "N/A"
        de_f = f"{c.get('debt_to_equity', 0.0):.2f}x" if pd.notna(c.get('debt_to_equity')) else "N/A"
        cagr_f = f"{c.get('sales_cagr_5yr', 0.0):.1f}%" if pd.notna(c.get('sales_cagr_5yr')) else "N/A"
        score_f = f"{c.get('composite_score', 0.0):.1f}" if pd.notna(c.get('composite_score')) else "N/A"
        
        master_table_data.append([
            Paragraph(c['company_id'], table_cell_style),
            Paragraph(c['company_name'][:22], table_cell_left_style),
            Paragraph(c['broad_sector'][:18], table_cell_left_style),
            Paragraph(weight_f, table_cell_style),
            Paragraph(mcap_f, table_cell_style),
            Paragraph(pe_f, table_cell_style),
            Paragraph(roe_f, table_cell_style),
            Paragraph(de_f, table_cell_style),
            Paragraph(cagr_f, table_cell_style),
            Paragraph(score_f, table_cell_style)
        ])
        
    master_table = Table(master_table_data, colWidths=[40, 100, 90, 45, 55, 30, 40, 45, 60, 35], repeatRows=1)
    master_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), color_primary),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOX', (0,0), (-1,-1), 0.5, color_border),
        ('INNERGRID', (0,0), (-1,-1), 0.5, color_border),
    ]))
    story.append(master_table)
    
    doc.build(story)
    logger.info(f"Portfolio Report PDF created successfully at {pdf_path}")

if __name__ == "__main__":
    generate_portfolio_pdf()
