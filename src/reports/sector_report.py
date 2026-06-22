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
OUTPUT_DIR = "reports/sectors"

def get_sector_data(sector_name: str, conn: sqlite3.Connection) -> dict:
    """Fetch sector summary metrics and list of constituents."""
    # 1. Fetch constituents
    query = """
    SELECT 
        s.company_id, c.company_name, s.index_weight_pct, s.sub_sector,
        cr.cluster_name,
        r.return_on_equity_pct, r.debt_to_equity, r.net_profit_margin_pct, r.operating_profit_margin_pct,
        mc.market_cap_crore, mc.pe_ratio, mc.dividend_yield_pct
    FROM sectors s
    JOIN companies c ON s.company_id = c.id
    LEFT JOIN company_clusters cr ON s.company_id = cr.company_id
    LEFT JOIN financial_ratios r ON s.company_id = r.company_id AND r.year = (
        SELECT MAX(year) FROM financial_ratios WHERE company_id = s.company_id
    )
    LEFT JOIN market_cap mc ON s.company_id = mc.company_id AND mc.year = 2024
    WHERE s.broad_sector = ?
    """
    df = pd.read_sql(query, conn, params=(sector_name,))
    if df.empty:
        return {}
        
    # Get 5-year CAGRs from screener data
    from src.analytics.screener.engine import get_latest_screener_data
    screener_df = get_latest_screener_data()
    cagr_subset = screener_df[['company_id', 'sales_cagr_5yr', 'pat_cagr_5yr', 'composite_score']].copy()
    
    df = df.merge(cagr_subset, on='company_id', how='left')
    
    # Calculate sector medians
    medians = {
        'roe': df['return_on_equity_pct'].median(),
        'de': df['debt_to_equity'].median(),
        'npm': df['net_profit_margin_pct'].median(),
        'opm': df['operating_profit_margin_pct'].median(),
        'pe': df['pe_ratio'].median(),
        'yield': df['dividend_yield_pct'].median(),
        'sales_cagr': df['sales_cagr_5yr'].median(),
        'pat_cagr': df['pat_cagr_5yr'].median(),
        'mcap': df['market_cap_crore'].sum()
    }
    
    # Identify top performers by composite score
    top_performers = df.sort_values(by='composite_score', ascending=False).head(3).to_dict(orient='records')
    
    return {
        'name': sector_name,
        'constituents': df.to_dict(orient='records'),
        'medians': medians,
        'top_performers': top_performers
    }

def generate_sector_pdf(sector_name: str, conn: sqlite3.Connection):
    """Compile ReportLab sector report PDF."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    # clean filename
    safe_name = "".join([c if c.isalnum() else "_" for c in sector_name])
    pdf_path = os.path.join(OUTPUT_DIR, f"{safe_name}_sector_report.pdf")
    
    data = get_sector_data(sector_name, conn)
    if not data:
        logger.error(f"No sector data found for: {sector_name}")
        return
        
    # Setup doc
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
        'SectorTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        textColor=color_primary,
        spaceAfter=3
    )
    
    subtitle_style = ParagraphStyle(
        'SectorSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        textColor=colors.HexColor('#57606a'),
        spaceAfter=15
    )
    
    section_title_style = ParagraphStyle(
        'SectorSecTitle',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        textColor=color_primary,
        spaceBefore=12,
        spaceAfter=6,
        borderColor=color_primary,
        borderWidth=0.5,
        borderPadding=2
    )
    
    body_style = ParagraphStyle(
        'SectorBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#0d1117')
    )
    
    table_hdr_style = ParagraphStyle(
        'TableHdr',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7,
        textColor=colors.white,
        alignment=1 # Centered
    )
    
    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        textColor=colors.HexColor('#24292f'),
        alignment=1
    )
    
    table_cell_left_style = ParagraphStyle(
        'TableCellLeft',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        textColor=colors.HexColor('#24292f'),
        alignment=0
    )

    story = []
    
    # Header
    story.append(Paragraph(f"{sector_name} Sector Report", title_style))
    meta_text = f"NIFTY 100 INDUSTRY INTELLIGENCE | CONSTITUENTS: {len(data['constituents'])} | TOTAL MARKET CAP: Rs {data['medians']['mcap']:,.0f} Cr"
    story.append(Paragraph(meta_text, subtitle_style))
    
    # Executive Summary
    story.append(Paragraph("Sector Overview & Market Weights", section_title_style))
    overview_text = (
        f"This report presents an aggregate fundaments and peer group analysis of the "
        f"{sector_name} sector, which represents a constituent weight in the Nifty 100 index. "
        f"The sector is analyzed across profit margins, capital structures, cash conversion, "
        f"and compound growth indicators over the historical 10-year cycle."
    )
    story.append(Paragraph(overview_text, body_style))
    story.append(Spacer(1, 10))
    
    # Medians Table
    story.append(Paragraph("Sector Median Performance Benchmarks", section_title_style))
    medians = data['medians']
    
    roe_m = f"{medians['roe']:.2f}%" if pd.notna(medians['roe']) else "N/A"
    de_m = f"{medians['de']:.2f}x" if pd.notna(medians['de']) else "N/A"
    npm_m = f"{medians['npm']:.2f}%" if pd.notna(medians['npm']) else "N/A"
    opm_m = f"{medians['opm']:.2f}%" if pd.notna(medians['opm']) else "N/A"
    pe_m = f"{medians['pe']:.2f}x" if pd.notna(medians['pe']) else "N/A"
    yield_m = f"{medians['yield']:.2f}%" if pd.notna(medians['yield']) else "N/A"
    sales_m = f"{medians['sales_cagr']:.2f}%" if pd.notna(medians['sales_cagr']) else "N/A"
    pat_m = f"{medians['pat_cagr']:.2f}%" if pd.notna(medians['pat_cagr']) else "N/A"
    
    med_table_data = [
        [
            Paragraph("Median ROE", table_hdr_style), Paragraph("Median D/E", table_hdr_style),
            Paragraph("Median NPM", table_hdr_style), Paragraph("Median OPM", table_hdr_style),
            Paragraph("Median P/E", table_hdr_style), Paragraph("Median Div Yield", table_hdr_style),
            Paragraph("Sales CAGR (5Yr)", table_hdr_style), Paragraph("PAT CAGR (5Yr)", table_hdr_style)
        ],
        [
            Paragraph(roe_m, table_cell_style), Paragraph(de_m, table_cell_style),
            Paragraph(npm_m, table_cell_style), Paragraph(opm_m, table_cell_style),
            Paragraph(pe_m, table_cell_style), Paragraph(yield_m, table_cell_style),
            Paragraph(sales_m, table_cell_style), Paragraph(pat_m, table_cell_style)
        ]
    ]
    med_table = Table(med_table_data, colWidths=[67.5]*8)
    med_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), color_primary),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOX', (0,0), (-1,-1), 1, color_border),
        ('INNERGRID', (0,0), (-1,-1), 0.5, color_border),
    ]))
    story.append(med_table)
    story.append(Spacer(1, 10))
    
    # Top Performers Highlight
    story.append(Paragraph("Top Performers (By Composite Scoring Matrix)", section_title_style))
    top_p_data = [["Rank", "Ticker", "Company Name", "ROE %", "D/E Ratio", "Sales CAGR (5Yr)", "Platform Score"]]
    for rank, p in enumerate(data['top_performers'], 1):
        top_p_data.append([
            f"#{rank}",
            p['company_id'],
            p['company_name'],
            f"{p['return_on_equity_pct']:.1f}%" if pd.notna(p['return_on_equity_pct']) else "N/A",
            f"{p['debt_to_equity']:.2f}x" if pd.notna(p['debt_to_equity']) else "N/A",
            f"{p['sales_cagr_5yr']:.1f}%" if pd.notna(p['sales_cagr_5yr']) else "N/A",
            f"{p['composite_score']:.1f}" if pd.notna(p['composite_score']) else "N/A"
        ])
    top_p_table = Table(top_p_data, colWidths=[40, 60, 160, 70, 70, 70, 70])
    top_p_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f6f8fa')),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('ALIGN', (2,1), (2,-1), 'LEFT'),
        ('FONTSIZE', (0,1), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('GRID', (0,0), (-1,-1), 0.5, color_border),
    ]))
    story.append(top_p_table)
    
    story.append(PageBreak())
    
    # Constituent Breakdown
    story.append(Paragraph(f"{sector_name} - Constituents Index List", section_title_style))
    
    hdr_row = [
        Paragraph("Ticker", table_hdr_style),
        Paragraph("Company Name", table_hdr_style),
        Paragraph("Sub-Sector", table_hdr_style),
        Paragraph("Market Cap", table_hdr_style),
        Paragraph("P/E Ratio", table_hdr_style),
        Paragraph("ROE %", table_hdr_style),
        Paragraph("D/E Ratio", table_hdr_style),
        Paragraph("Sales CAGR", table_hdr_style)
    ]
    breakdown_data = [hdr_row]
    
    # Sort constituents alphabetically by company name
    constituents = sorted(data['constituents'], key=lambda x: x['company_name'])
    
    for c in constituents:
        mcap_f = f"{c.get('market_cap_crore', 0.0):,.0f}" if pd.notna(c.get('market_cap_crore')) else "N/A"
        pe_f = f"{c.get('pe_ratio', 0.0):.1f}x" if pd.notna(c.get('pe_ratio')) else "N/A"
        roe_f = f"{c.get('return_on_equity_pct', 0.0):.1f}%" if pd.notna(c.get('return_on_equity_pct')) else "N/A"
        de_f = f"{c.get('debt_to_equity', 0.0):.2f}x" if pd.notna(c.get('debt_to_equity')) else "N/A"
        cagr_f = f"{c.get('sales_cagr_5yr', 0.0):.1f}%" if pd.notna(c.get('sales_cagr_5yr')) else "N/A"
        
        breakdown_data.append([
            Paragraph(c['company_id'], table_cell_style),
            Paragraph(c['company_name'][:28], table_cell_left_style),
            Paragraph(c['sub_sector'][:20], table_cell_left_style),
            Paragraph(mcap_f, table_cell_style),
            Paragraph(pe_f, table_cell_style),
            Paragraph(roe_f, table_cell_style),
            Paragraph(de_f, table_cell_style),
            Paragraph(cagr_f, table_cell_style)
        ])
        
    breakdown_table = Table(breakdown_data, colWidths=[55, 120, 105, 55, 45, 45, 55, 60])
    breakdown_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), color_primary),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOX', (0,0), (-1,-1), 0.5, color_border),
        ('INNERGRID', (0,0), (-1,-1), 0.5, color_border),
    ]))
    story.append(breakdown_table)
    
    doc.build(story)
    logger.info(f"Sector Report PDF created successfully for {sector_name} at {pdf_path}")

def generate_all_sectors():
    """Builds reports for all unique broad sectors in database."""
    conn = sqlite3.connect(DB_PATH)
    sectors = pd.read_sql("SELECT DISTINCT broad_sector FROM sectors", conn)['broad_sector'].tolist()
    
    logger.info(f"Starting Sector Report generation for {len(sectors)} sectors...")
    for s in sectors:
        if s and s != "N/A":
            try:
                generate_sector_pdf(s, conn)
            except Exception as e:
                logger.error(f"Failed to generate report for sector {s}: {e}", exc_info=True)
    conn.close()
    logger.info("Sector Report generation complete.")

if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    generate_sector_pdf("Financials", conn)
    conn.close()
