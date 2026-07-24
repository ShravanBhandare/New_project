"""
src/reports/sector_report.py

Generates executive sector benchmark report PDFs for all 11 peer groups.
Each PDF includes:
- Sector summary header and key median KPI tiles
- Sector peer comparison chart (ROE vs Revenue CAGR)
- Complete constituent table with 8 key metrics per company and sector median summary row
- ReportLab styling with strict wordwrap and explicit column widths
"""

import os
import io
import re
import sqlite3
import logging
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
)
from reportlab.pdfgen.canvas import Canvas

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "nifty100.db")


class NumberedCanvas(Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#7F8C8D"))
        # Footer line
        width = 792  # Landscape Letter width
        self.setStrokeColor(colors.HexColor("#BDC3C7"))
        self.setLineWidth(0.5)
        self.line(28.8, 25, width - 28.8, 25)
        # Footer text
        self.drawString(28.8, 14, "Nifty 100 Financial Analytics | Sector Benchmark Report")
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(width - 28.8, 14, page_text)
        self.restoreState()


def get_db_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    return sqlite3.connect(db_path)


def fetch_sector_data(peer_group_name: str, db_path: str = DB_PATH) -> dict:
    """Fetch company metrics and sector medians for a given peer group."""
    conn = get_db_connection(db_path)
    
    query = """
        SELECT DISTINCT c.id as company_id, c.company_name, s.broad_sector,
               mc.market_cap_crore, mc.pe_ratio,
               fr.return_on_equity_pct, fr.return_on_capital_employed_pct,
               fr.debt_to_equity, fr.sales_cagr_5yr, fr.free_cash_flow_cr
        FROM peer_percentiles pp
        JOIN companies c ON pp.company_id = c.id
        LEFT JOIN sectors s ON c.id = s.company_id
        LEFT JOIN market_cap mc ON c.id = mc.company_id AND mc.year = 2024
        LEFT JOIN financial_ratios fr ON c.id = fr.company_id AND fr.year = '2024-03'
        WHERE pp.peer_group_name = ?
        ORDER BY mc.market_cap_crore DESC
    """
    df = pd.read_sql(query, conn, params=(peer_group_name,))
    conn.close()
    
    if df.empty:
        raise ValueError(f"No companies found for sector / peer group '{peer_group_name}'.")

    # Compute Medians
    medians = {
        'market_cap_crore': df['market_cap_crore'].median(),
        'pe_ratio': df['pe_ratio'].median(),
        'return_on_equity_pct': df['return_on_equity_pct'].median(),
        'return_on_capital_employed_pct': df['return_on_capital_employed_pct'].median(),
        'debt_to_equity': df['debt_to_equity'].median(),
        'sales_cagr_5yr': df['sales_cagr_5yr'].median(),
        'free_cash_flow_cr': df['free_cash_flow_cr'].median()
    }
    
    return {
        'peer_group_name': peer_group_name,
        'broad_sector': df.iloc[0]['broad_sector'] if not df.empty and pd.notna(df.iloc[0]['broad_sector']) else peer_group_name,
        'companies_df': df,
        'medians': medians
    }


def create_sector_bar_chart(df: pd.DataFrame, peer_group_name: str) -> io.BytesIO:
    """Generate side-by-side bar chart of ROE (%) and 5Y Revenue CAGR (%) for companies in sector."""
    fig, ax = plt.subplots(figsize=(10, 2.3), dpi=180)
    
    comp_ids = df['company_id'].tolist()
    roe_vals = df['return_on_equity_pct'].fillna(0).values
    cagr_vals = df['sales_cagr_5yr'].fillna(0).values
    
    x = np.arange(len(comp_ids))
    width = 0.35
    
    ax.bar(x - width/2, roe_vals, width, label='ROE (%)', color='#1A2B4C')
    ax.bar(x + width/2, cagr_vals, width, label='5Y Rev CAGR (%)', color='#008080')
    
    ax.set_xticks(x)
    ax.set_xticklabels(comp_ids, fontsize=8.5, fontweight='bold', rotation=0)
    ax.tick_params(axis='y', labelsize=8)
    ax.set_title(f'{peer_group_name} — Company ROE (%) vs 5-Year Revenue CAGR (%)', fontsize=10, fontweight='bold', color='#1A2B4C', pad=4)
    ax.legend(fontsize=8, loc='upper right', frameon=True, facecolor='#FFFFFF', edgecolor='#DFE4EA')
    ax.axhline(0, color='#2C3E50', linewidth=0.8)
    ax.grid(axis='y', linestyle='--', alpha=0.4)
    ax.set_axisbelow(True)
    
    plt.tight_layout(pad=0.5)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=180)
    plt.close(fig)
    buf.seek(0)
    return buf


def generate_sector_report(peer_group_name: str, output_path: str = None) -> str:
    """
    Generate an executive landscape PDF sector benchmark report for a given peer group.
    """
    data = fetch_sector_data(peer_group_name)
    df = data['companies_df']
    med = data['medians']
    
    if not output_path:
        out_dir = os.path.join(os.path.dirname(__file__), "..", "..", "reports", "sector")
        os.makedirs(out_dir, exist_ok=True)
        # Clean sector name for output filename
        safe_name = peer_group_name.replace(" ", "_")
        output_path = os.path.join(out_dir, f"{safe_name}_report.pdf")
    else:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    # Use Landscape Letter (792 x 612 pt) for wide tables
    doc = SimpleDocTemplate(
        output_path,
        pagesize=landscape(letter),
        leftMargin=28.8,
        rightMargin=28.8,
        topMargin=28.8,
        bottomMargin=28.8
    )
    
    printable_width = 792 - 57.6  # 734.4 pt
    styles = getSampleStyleSheet()
    
    style_header_title = ParagraphStyle('SecReportTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=16, textColor=colors.white, leading=19)
    style_header_sub = ParagraphStyle('SecReportSub', parent=styles['Normal'], fontName='Helvetica', fontSize=9, textColor=colors.HexColor('#CED6E0'), leading=11)
    style_header_tag = ParagraphStyle('SecReportTag', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, textColor=colors.HexColor('#ECCC68'), alignment=2, leading=13)
    
    style_kpi_label = ParagraphStyle('SecKPILabel', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=7.5, textColor=colors.HexColor('#57606F'), alignment=1, leading=9)
    style_kpi_val = ParagraphStyle('SecKPIVal', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, textColor=colors.HexColor('#1A2B4C'), alignment=1, leading=13)
    
    style_th = ParagraphStyle('TableHead', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, textColor=colors.white, alignment=1, leading=10)
    style_td = ParagraphStyle('TableData', parent=styles['Normal'], fontName='Helvetica', fontSize=8, textColor=colors.HexColor('#2C3E50'), leading=10, wordWrap='CJK')
    style_td_bold = ParagraphStyle('TableDataBold', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, textColor=colors.HexColor('#1A2B4C'), leading=10, wordWrap='CJK')
    style_td_med = ParagraphStyle('TableDataMed', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8.5, textColor=colors.HexColor('#1A2B4C'), leading=10, wordWrap='CJK')

    story = []

    # 1. Navy Header Bar
    p_title = Paragraph(f"{peer_group_name.upper()} SECTOR BENCHMARK REPORT", style_header_title)
    p_sub = Paragraph(f"Broad Sector: <b>{data['broad_sector']}</b> &nbsp;|&nbsp; <b>{len(df)} Companies Analyzed</b>", style_header_sub)
    p_tag = Paragraph("NIFTY 100 ANALYTICS<br/><font color='#CED6E0' size=8>FY 2024 Benchmark</font>", style_header_tag)
    
    header_table = Table([[p_title, p_tag], [p_sub, '']], colWidths=[printable_width * 0.70, printable_width * 0.30])
    header_table.setStyle(TableStyle([
        ('SPAN', (1, 0), (1, 1)),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#1A2B4C')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 6))

    # 2. Sector Median KPI Tiles (1 row of 6 tiles)
    def fmt(val, fmt_str, default="N/A"):
        return fmt_str.format(val) if val is not None and pd.notna(val) else default

    med_mcap = f"₹{med['market_cap_crore']:,.0f} Cr" if pd.notna(med['market_cap_crore']) else "N/A"
    med_pe = fmt(med['pe_ratio'], "{:.1f}x")
    med_roe = fmt(med['return_on_equity_pct'], "{:.1f}%")
    med_roce = fmt(med['return_on_capital_employed_pct'], "{:.1f}%")
    med_de = "Suppressed (Fin)" if data['broad_sector'] == 'Financials' else fmt(med['debt_to_equity'], "{:.2f}")
    med_cagr = fmt(med['sales_cagr_5yr'], "{:.1f}%")
    med_fcf = f"₹{med['free_cash_flow_cr']:,.0f} Cr" if pd.notna(med['free_cash_flow_cr']) else "N/A"

    tiles_data = [[
        [Paragraph("MEDIAN MCAP", style_kpi_label), Paragraph(med_mcap, style_kpi_val)],
        [Paragraph("MEDIAN P/E", style_kpi_label), Paragraph(med_pe, style_kpi_val)],
        [Paragraph("MEDIAN ROE", style_kpi_label), Paragraph(med_roe, style_kpi_val)],
        [Paragraph("MEDIAN ROCE", style_kpi_label), Paragraph(med_roce, style_kpi_val)],
        [Paragraph("MEDIAN D/E", style_kpi_label), Paragraph(med_de, style_kpi_val)],
        [Paragraph("MEDIAN 5Y CAGR", style_kpi_label), Paragraph(med_cagr, style_kpi_val)]
    ]]
    
    tile_w = printable_width / 6.0
    kpi_table = Table(tiles_data, colWidths=[tile_w]*6)
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8F9FA')),
        ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor('#1A2B4C')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#DFE4EA')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 6))

    # 3. Sector Chart
    chart_buf = create_sector_bar_chart(df, peer_group_name)
    story.append(Image(chart_buf, width=printable_width, height=170))
    story.append(Spacer(1, 6))

    # 4. Constituent Table (8 key metrics per company + Median row)
    headers = [
        Paragraph("Ticker", style_th),
        Paragraph("Company Name", style_th),
        Paragraph("Market Cap (₹ Cr)", style_th),
        Paragraph("P/E Ratio", style_th),
        Paragraph("ROE (%)", style_th),
        Paragraph("ROCE (%)", style_th),
        Paragraph("D/E Ratio", style_th),
        Paragraph("5Y Rev CAGR", style_th),
        Paragraph("FCF (₹ Cr)", style_th)
    ]
    
    table_rows = [headers]
    
    for _, row in df.iterrows():
        c_de = "Suppressed" if data['broad_sector'] == 'Financials' else fmt(row['debt_to_equity'], "{:.2f}")
        c_fcf = f"₹{row['free_cash_flow_cr']:,.0f}" if pd.notna(row['free_cash_flow_cr']) else "N/A"
        
        table_rows.append([
            Paragraph(f"<b>{row['company_id']}</b>", style_td_bold),
            Paragraph(str(row['company_name']), style_td),
            Paragraph(f"₹{row['market_cap_crore']:,.0f}" if pd.notna(row['market_cap_crore']) else "N/A", style_td),
            Paragraph(fmt(row['pe_ratio'], "{:.1f}x"), style_td),
            Paragraph(fmt(row['return_on_equity_pct'], "{:.1f}%"), style_td),
            Paragraph(fmt(row['return_on_capital_employed_pct'], "{:.1f}%"), style_td),
            Paragraph(c_de, style_td),
            Paragraph(fmt(row['sales_cagr_5yr'], "{:.1f}%"), style_td),
            Paragraph(c_fcf, style_td)
        ])
        
    # Append Sector Median Summary Row
    table_rows.append([
        Paragraph("<b>MEDIAN</b>", style_td_med),
        Paragraph(f"<b>{peer_group_name} Sector Median</b>", style_td_med),
        Paragraph(f"<b>{med_mcap}</b>", style_td_med),
        Paragraph(f"<b>{med_pe}</b>", style_td_med),
        Paragraph(f"<b>{med_roe}</b>", style_td_med),
        Paragraph(f"<b>{med_roce}</b>", style_td_med),
        Paragraph(f"<b>{med_de}</b>", style_td_med),
        Paragraph(f"<b>{med_cagr}</b>", style_td_med),
        Paragraph(f"<b>{med_fcf}</b>", style_td_med)
    ])

    col_widths = [65, 170, 85, 55, 60, 60, 75, 75, 89.4]
    comp_table = Table(table_rows, colWidths=col_widths, repeatRows=1)
    
    table_style = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1A2B4C')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#DFE4EA')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        # Highlight Median Row
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#F1C40F')),
    ]
    
    # Alternating row colors
    for r in range(1, len(table_rows) - 1):
        if r % 2 == 0:
            table_style.append(('BACKGROUND', (0, r), (-1, r), colors.HexColor('#F8F9FA')))

    comp_table.setStyle(TableStyle(table_style))
    story.append(comp_table)

    doc.build(story, canvasmaker=NumberedCanvas)
    
    with open(output_path, 'rb') as f:
        content = f.read()
    page_count = len(re.findall(rb'/Type\s*/Page[^s]', content))
    logger.info(f"Generated sector report for '{peer_group_name}' -> {output_path} (Pages: {page_count})")
    
    return output_path


def generate_all_sector_reports(db_path: str = DB_PATH) -> list:
    """Generate all 11 sector report PDFs."""
    conn = get_db_connection(db_path)
    groups = pd.read_sql("SELECT DISTINCT peer_group_name FROM peer_percentiles ORDER BY peer_group_name", conn)['peer_group_name'].tolist()
    conn.close()
    
    out_paths = []
    print(f"=== BATCH SECTOR REPORT GENERATION ({len(groups)} SECTORS) ===")
    for g in groups:
        path = generate_sector_report(g)
        out_paths.append(path)
        print(f"[OK] {g:<20} -> {path}")
        
    return out_paths


if __name__ == "__main__":
    generate_all_sector_reports()
