"""
src/reports/tearsheet.py

Generates a 2-page executive company tearsheet using ReportLab and Matplotlib.

Page 1:
- Navy Header Bar with Company Name, Ticker, Sector, Sub-Sector
- 6 KPI Tiles in 2 rows of 3
- 10-Year Revenue and Net Profit grouped bar chart
- ROE and ROCE dual line chart

Page 2:
- Balance Sheet composition stacked bar chart
- Cash Flow waterfall / bar chart for latest financial year
- Pros section (green bullets)
- Cons section (red bullets)
- Capital Allocation pattern badge
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

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, KeepTogether
)
from reportlab.pdfgen.canvas import Canvas

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "nifty100.db")
PROS_CONS_CSV = os.path.join(os.path.dirname(__file__), "..", "..", "output", "pros_cons_generated.csv")


class NumberedCanvas(Canvas):
    """
    Two-pass canvas to dynamically compute total pages and draw footer.
    """
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
        self.setStrokeColor(colors.HexColor("#BDC3C7"))
        self.setLineWidth(0.5)
        self.line(28.8, 25, 612 - 28.8, 25)
        # Footer text
        self.drawString(28.8, 14, "Nifty 100 Financial Analytics | Executive Tearsheet")
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(612 - 28.8, 14, page_text)
        self.restoreState()


def get_db_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    return sqlite3.connect(db_path)


def fetch_tearsheet_data(company_id: str, db_path: str = DB_PATH) -> dict:
    """
    Fetch all financial metrics, series, and pros/cons for a company.
    """
    conn = get_db_connection(db_path)
    
    # 1. Company Metadata
    df_comp = pd.read_sql("SELECT id, company_name FROM companies WHERE id = ?", conn, params=(company_id,))
    if df_comp.empty:
        conn.close()
        raise ValueError(f"Company ID '{company_id}' not found in database.")
    company_name = df_comp.iloc[0]['company_name']
    
    # 2. Sector Info
    df_sec = pd.read_sql("SELECT broad_sector, sub_sector FROM sectors WHERE company_id = ?", conn, params=(company_id,))
    broad_sector = df_sec.iloc[0]['broad_sector'] if not df_sec.empty else 'N/A'
    sub_sector = df_sec.iloc[0]['sub_sector'] if not df_sec.empty else 'N/A'
    
    # 3. Market Cap & Valuation (2024)
    df_mc = pd.read_sql("SELECT market_cap_crore, pe_ratio, pb_ratio FROM market_cap WHERE company_id = ? AND year = 2024", conn, params=(company_id,))
    mcap = df_mc.iloc[0]['market_cap_crore'] if not df_mc.empty and pd.notna(df_mc.iloc[0]['market_cap_crore']) else None
    pe = df_mc.iloc[0]['pe_ratio'] if not df_mc.empty and pd.notna(df_mc.iloc[0]['pe_ratio']) else None
    pb = df_mc.iloc[0]['pb_ratio'] if not df_mc.empty and pd.notna(df_mc.iloc[0]['pb_ratio']) else None
    
    # 4. Ratios (Latest full year: 2024-03)
    df_ratios_latest = pd.read_sql(
        "SELECT return_on_equity_pct, return_on_capital_employed_pct, debt_to_equity, free_cash_flow_cr, capital_allocation_pattern, sales_cagr_5yr "
        "FROM financial_ratios WHERE company_id = ? AND year = '2024-03'",
        conn, params=(company_id,)
    )
    if df_ratios_latest.empty:
        df_ratios_latest = pd.read_sql(
            "SELECT return_on_equity_pct, return_on_capital_employed_pct, debt_to_equity, free_cash_flow_cr, capital_allocation_pattern, sales_cagr_5yr "
            "FROM financial_ratios WHERE company_id = ? AND year LIKE '%-03' ORDER BY year DESC LIMIT 1",
            conn, params=(company_id,)
        )
    
    roe = df_ratios_latest.iloc[0]['return_on_equity_pct'] if not df_ratios_latest.empty else None
    roce = df_ratios_latest.iloc[0]['return_on_capital_employed_pct'] if not df_ratios_latest.empty else None
    de = df_ratios_latest.iloc[0]['debt_to_equity'] if not df_ratios_latest.empty else None
    fcf = df_ratios_latest.iloc[0]['free_cash_flow_cr'] if not df_ratios_latest.empty else None
    cap_alloc = df_ratios_latest.iloc[0]['capital_allocation_pattern'] if not df_ratios_latest.empty else 'N/A'
    rev_cagr = df_ratios_latest.iloc[0]['sales_cagr_5yr'] if not df_ratios_latest.empty else None
    
    # 5. 10-Year Historical Financial Series (Annual ending -03)
    df_pl = pd.read_sql(
        "SELECT year, sales, net_profit FROM profitandloss WHERE company_id = ? AND year LIKE '%-03' ORDER BY year",
        conn, params=(company_id,)
    )
    df_bs = pd.read_sql(
        "SELECT year, equity_capital, reserves, borrowings, other_liabilities FROM balancesheet WHERE company_id = ? AND year LIKE '%-03' ORDER BY year",
        conn, params=(company_id,)
    )
    df_ratios_hist = pd.read_sql(
        "SELECT year, return_on_equity_pct, return_on_capital_employed_pct FROM financial_ratios WHERE company_id = ? AND year LIKE '%-03' ORDER BY year",
        conn, params=(company_id,)
    )
    
    # 6. Latest Cash Flow (2024-03)
    df_cf = pd.read_sql(
        "SELECT year, operating_activity, investing_activity, financing_activity, net_cash_flow "
        "FROM cashflow WHERE company_id = ? AND year = '2024-03'",
        conn, params=(company_id,)
    )
    if df_cf.empty:
        df_cf = pd.read_sql(
            "SELECT year, operating_activity, investing_activity, financing_activity, net_cash_flow "
            "FROM cashflow WHERE company_id = ? AND year LIKE '%-03' ORDER BY year DESC LIMIT 1",
            conn, params=(company_id,)
        )
    
    conn.close()
    
    # 7. Pros & Cons
    pros = []
    cons = []
    if os.path.exists(PROS_CONS_CSV):
        df_pc = pd.read_csv(PROS_CONS_CSV)
        sub_pc = df_pc[df_pc['company_id'] == company_id]
        pros = sub_pc[sub_pc['type'] == 'pro']['text'].tolist()
        cons = sub_pc[sub_pc['type'] == 'con']['text'].tolist()
    
    if not pros:
        pros = ["Demonstrates robust industry presence and operational scale."]
    if not cons:
        cons = ["Subject to broader macroeconomic and industry cyclicality."]

    return {
        'company_id': company_id,
        'company_name': company_name,
        'broad_sector': broad_sector,
        'sub_sector': sub_sector,
        'mcap': mcap,
        'pe': pe,
        'pb': pb,
        'roe': roe,
        'roce': roce,
        'de': de,
        'fcf': fcf,
        'cap_alloc': cap_alloc,
        'rev_cagr': rev_cagr,
        'pl_history': df_pl,
        'bs_history': df_bs,
        'ratios_history': df_ratios_hist,
        'cf_latest': df_cf,
        'pros': pros,
        'cons': cons
    }


# ==============================================================================
# CHART GENERATORS (Matplotlib -> BytesIO -> ReportLab Image)
# ==============================================================================

def create_revenue_profit_chart(df_pl: pd.DataFrame) -> io.BytesIO:
    """Generate 10-year Revenue and Net Profit grouped bar chart."""
    fig, ax = plt.subplots(figsize=(7.5, 2.2), dpi=180)
    
    if not df_pl.empty:
        df = df_pl.tail(10).copy()
        years = [str(y).replace('-03', '') for y in df['year']]
        sales = df['sales'].fillna(0).values
        profit = df['net_profit'].fillna(0).values
        
        x = np.arange(len(years))
        width = 0.38
        
        rects1 = ax.bar(x - width/2, sales, width, label='Sales (₹ Cr)', color='#1A2B4C')
        rects2 = ax.bar(x + width/2, profit, width, label='Net Profit (₹ Cr)', color='#008080')
        
        ax.set_xticks(x)
        ax.set_xticklabels(years, fontsize=7.5, fontweight='bold')
        ax.tick_params(axis='y', labelsize=7.5)
        ax.set_title('10-Year Revenue & Net Profit Trend (₹ Crore)', fontsize=9, fontweight='bold', color='#1A2B4C', pad=4)
        ax.legend(fontsize=7.5, loc='upper left', frameon=True, facecolor='#FFFFFF', edgecolor='#DFE4EA')
        ax.grid(axis='y', linestyle='--', alpha=0.4)
        ax.set_axisbelow(True)
    else:
        ax.text(0.5, 0.5, 'No Profit & Loss Data Available', ha='center', va='center')

    plt.tight_layout(pad=0.5)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=180)
    plt.close(fig)
    buf.seek(0)
    return buf


def create_roe_roce_chart(df_ratios: pd.DataFrame) -> io.BytesIO:
    """Generate ROE & ROCE line chart over 10 years."""
    fig, ax = plt.subplots(figsize=(7.5, 2.2), dpi=180)
    
    if not df_ratios.empty:
        df = df_ratios.tail(10).copy()
        years = [str(y).replace('-03', '') for y in df['year']]
        roe_vals = df['return_on_equity_pct'].values
        roce_vals = df['return_on_capital_employed_pct'].values
        
        x = np.arange(len(years))
        
        ax.plot(x, roe_vals, marker='o', linewidth=2, color='#27AE60', label='ROE (%)')
        ax.plot(x, roce_vals, marker='s', linewidth=2, color='#C0392B', label='ROCE (%)')
        ax.axhline(15, color='#7F8C8D', linestyle='--', linewidth=1, alpha=0.7, label='15% Benchmark')
        
        ax.set_xticks(x)
        ax.set_xticklabels(years, fontsize=7.5, fontweight='bold')
        ax.tick_params(axis='y', labelsize=7.5)
        ax.set_title('10-Year ROE & ROCE Efficiency Trend (%)', fontsize=9, fontweight='bold', color='#1A2B4C', pad=4)
        ax.legend(fontsize=7.5, loc='upper left', frameon=True, facecolor='#FFFFFF', edgecolor='#DFE4EA')
        ax.grid(axis='both', linestyle='--', alpha=0.4)
        ax.set_axisbelow(True)
    else:
        ax.text(0.5, 0.5, 'No Ratio History Available', ha='center', va='center')

    plt.tight_layout(pad=0.5)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=180)
    plt.close(fig)
    buf.seek(0)
    return buf


def create_balance_sheet_stacked_chart(df_bs: pd.DataFrame) -> io.BytesIO:
    """Generate Balance Sheet composition stacked bar chart."""
    fig, ax = plt.subplots(figsize=(7.5, 2.1), dpi=180)
    
    if not df_bs.empty:
        df = df_bs.tail(10).copy()
        years = [str(y).replace('-03', '') for y in df['year']]
        
        equity = (df['equity_capital'].fillna(0) + df['reserves'].fillna(0)).values
        borrowings = df['borrowings'].fillna(0).values
        other_liab = df['other_liabilities'].fillna(0).values
        
        x = np.arange(len(years))
        width = 0.5
        
        ax.bar(x, equity, width, label='Net Worth (Equity+Res)', color='#1A2B4C')
        ax.bar(x, borrowings, width, bottom=equity, label='Borrowings', color='#E74C3C')
        ax.bar(x, other_liab, width, bottom=equity+borrowings, label='Other Liabilities', color='#95A5A6')
        
        ax.set_xticks(x)
        ax.set_xticklabels(years, fontsize=7.5, fontweight='bold')
        ax.tick_params(axis='y', labelsize=7.5)
        ax.set_title('10-Year Balance Sheet Capital Structure (₹ Crore)', fontsize=9, fontweight='bold', color='#1A2B4C', pad=4)
        ax.legend(fontsize=7.5, loc='upper left', frameon=True, facecolor='#FFFFFF', edgecolor='#DFE4EA')
        ax.grid(axis='y', linestyle='--', alpha=0.4)
        ax.set_axisbelow(True)
    else:
        ax.text(0.5, 0.5, 'No Balance Sheet History Available', ha='center', va='center')

    plt.tight_layout(pad=0.5)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=180)
    plt.close(fig)
    buf.seek(0)
    return buf


def create_cashflow_waterfall_chart(df_cf: pd.DataFrame) -> io.BytesIO:
    """Generate Cash Flow breakdown bar chart for the latest financial year."""
    fig, ax = plt.subplots(figsize=(7.5, 1.9), dpi=180)
    
    if not df_cf.empty:
        row = df_cf.iloc[0]
        yr = str(row['year']).replace('-03', '')
        cfo = float(row['operating_activity']) if pd.notna(row['operating_activity']) else 0.0
        cfi = float(row['investing_activity']) if pd.notna(row['investing_activity']) else 0.0
        cff = float(row['financing_activity']) if pd.notna(row['financing_activity']) else 0.0
        net = float(row['net_cash_flow']) if pd.notna(row['net_cash_flow']) else (cfo + cfi + cff)
        
        categories = ['Operating (CFO)', 'Investing (CFI)', 'Financing (CFF)', 'Net Cash Flow']
        values = [cfo, cfi, cff, net]
        bar_colors = ['#2ECC71' if v >= 0 else '#E74C3C' for v in values[:-1]] + ['#1A2B4C']
        
        x = np.arange(len(categories))
        rects = ax.bar(x, values, color=bar_colors, width=0.45)
        
        # Add text labels on top/bottom of bars
        for rect, val in zip(rects, values):
            h = rect.get_height()
            va = 'bottom' if h >= 0 else 'top'
            y_pos = h + (max(abs(val) for val in values)*0.03 if h >= 0 else -max(abs(val) for val in values)*0.08)
            ax.annotate(f'₹{val:,.0f}',
                        xy=(rect.get_x() + rect.get_width() / 2, y_pos),
                        xytext=(0, 0), textcoords="offset points",
                        ha='center', va=va, fontsize=7.5, fontweight='bold')
        
        ax.set_xticks(x)
        ax.set_xticklabels(categories, fontsize=7.5, fontweight='bold')
        ax.tick_params(axis='y', labelsize=7.5)
        ax.set_title(f'Latest Cash Flow Breakdown (FY{yr} ₹ Crore)', fontsize=9, fontweight='bold', color='#1A2B4C', pad=4)
        ax.axhline(0, color='#2C3E50', linewidth=0.8)
        ax.grid(axis='y', linestyle='--', alpha=0.4)
        ax.set_axisbelow(True)
    else:
        ax.text(0.5, 0.5, 'No Cash Flow Data Available', ha='center', va='center')

    plt.tight_layout(pad=0.5)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=180)
    plt.close(fig)
    buf.seek(0)
    return buf


# ==============================================================================
# MAIN TEARSHEET GENERATOR
# ==============================================================================

def generate_tearsheet(company_id: str, output_path: str = None) -> str:
    """
    Generate a strict 2-page company tearsheet PDF.
    
    Parameters:
    - company_id: Company ticker symbol (e.g., 'TCS', 'HDFCBANK')
    - output_path: Optional custom path for generated PDF
    
    Returns:
    - Path to the generated PDF file.
    """
    data = fetch_tearsheet_data(company_id)
    
    if not output_path:
        out_dir = os.path.join(os.path.dirname(__file__), "..", "..", "output", "tearsheets")
        os.makedirs(out_dir, exist_ok=True)
        output_path = os.path.join(out_dir, f"{company_id}_tearsheet.pdf")
    else:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=28.8,
        rightMargin=28.8,
        topMargin=28.8,
        bottomMargin=28.8
    )
    
    printable_width = 612 - 57.6  # 554.4 pt
    styles = getSampleStyleSheet()
    
    # Custom Paragraph Styles
    style_header_title = ParagraphStyle('HeaderTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=15, textColor=colors.white, leading=18)
    style_header_ticker = ParagraphStyle('HeaderTicker', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=12, textColor=colors.HexColor('#70A1FF'), leading=15)
    style_header_sub = ParagraphStyle('HeaderSub', parent=styles['Normal'], fontName='Helvetica', fontSize=8.5, textColor=colors.HexColor('#CED6E0'), leading=11)
    style_header_tag = ParagraphStyle('HeaderTag', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, textColor=colors.HexColor('#ECCC68'), alignment=2, leading=13)
    
    style_kpi_label = ParagraphStyle('KPILabel', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=7.5, textColor=colors.HexColor('#57606F'), alignment=1, leading=9)
    style_kpi_val = ParagraphStyle('KPIVal', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, textColor=colors.HexColor('#1A2B4C'), alignment=1, leading=13)
    
    style_sec_header = ParagraphStyle('SecHeader', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leading=12)
    style_bullet_pro = ParagraphStyle('BulletPro', parent=styles['Normal'], fontName='Helvetica', fontSize=8, textColor=colors.HexColor('#1E8449'), leading=10, wordWrap='CJK')
    style_bullet_con = ParagraphStyle('BulletCon', parent=styles['Normal'], fontName='Helvetica', fontSize=8, textColor=colors.HexColor('#C0392B'), leading=10, wordWrap='CJK')
    style_badge = ParagraphStyle('BadgeText', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, textColor=colors.white, alignment=1, leading=11)

    story = []

    # ==========================================================================
    # PAGE 1 LAYOUT
    # ==========================================================================
    
    # 1. Navy Header Bar
    p_title = Paragraph(f"{data['company_name']} <font color='#70A1FF'>({data['company_id']})</font>", style_header_title)
    p_sec = Paragraph(f"Broad Sector: <b>{data['broad_sector']}</b> &nbsp;|&nbsp; Sub-Sector: <b>{data['sub_sector']}</b>", style_header_sub)
    p_tag = Paragraph("NIFTY 100 FINANCIAL TEARSHEET<br/><font color='#CED6E0' size=8>Latest FY 2024-03</font>", style_header_tag)
    
    header_data = [[p_title, p_tag], [p_sec, '']]
    header_table = Table(header_data, colWidths=[printable_width * 0.70, printable_width * 0.30])
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

    # 2. 6 KPI Tiles (2 rows of 3)
    def fmt_val(val, fmt_str, default="N/A"):
        return fmt_str.format(val) if val is not None and pd.notna(val) else default

    mcap_str = f"₹{data['mcap']:,.0f} Cr" if data['mcap'] is not None and pd.notna(data['mcap']) else "N/A"
    pe_str = fmt_val(data['pe'], "{:.1f}x")
    roe_str = fmt_val(data['roe'], "{:.1f}%")
    cagr_str = fmt_val(data['rev_cagr'], "{:.1f}%")
    
    if data['broad_sector'] == 'Financials':
        de_str = "Suppressed (Fin)"
    else:
        de_str = fmt_val(data['de'], "{:.2f}") if data['de'] is not None and data['de'] > 0 else "0.00 (Debt Free)"
        
    fcf_str = f"₹{data['fcf']:,.0f} Cr" if data['fcf'] is not None and pd.notna(data['fcf']) else "N/A"

    tiles_data = [
        [
            [Paragraph("MARKET CAP", style_kpi_label), Paragraph(mcap_str, style_kpi_val)],
            [Paragraph("P/E RATIO", style_kpi_label), Paragraph(pe_str, style_kpi_val)],
            [Paragraph("RETURN ON EQUITY (ROE)", style_kpi_label), Paragraph(roe_str, style_kpi_val)]
        ],
        [
            [Paragraph("5Y REVENUE CAGR", style_kpi_label), Paragraph(cagr_str, style_kpi_val)],
            [Paragraph("DEBT TO EQUITY (D/E)", style_kpi_label), Paragraph(de_str, style_kpi_val)],
            [Paragraph("FREE CASH FLOW (FCF)", style_kpi_label), Paragraph(fcf_str, style_kpi_val)]
        ]
    ]

    col_w = printable_width / 3.0
    kpi_table = Table(tiles_data, colWidths=[col_w, col_w, col_w])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8F9FA')),
        ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor('#1A2B4C')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#DFE4EA')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 6))

    # 3. Chart 1: Revenue & Net Profit Bar Chart
    buf_chart1 = create_revenue_profit_chart(data['pl_history'])
    img_chart1 = Image(buf_chart1, width=printable_width, height=168)
    story.append(img_chart1)
    story.append(Spacer(1, 6))

    # 4. Chart 2: ROE & ROCE Dual Line Chart
    buf_chart2 = create_roe_roce_chart(data['ratios_history'])
    img_chart2 = Image(buf_chart2, width=printable_width, height=168)
    story.append(img_chart2)

    # PAGE BREAK TO ENSURE STRICT 2-PAGE BUDGET
    story.append(PageBreak())

    # ==========================================================================
    # PAGE 2 LAYOUT
    # ==========================================================================
    
    # 1. Page 2 Navy Header Bar
    p_p2_title = Paragraph(f"<b>{data['company_name']} ({data['company_id']})</b> — Capital Structure & Qualitative Analysis", style_header_title)
    p_p2_tag = Paragraph("PAGE 2 OF 2", style_header_tag)
    p2_header_table = Table([[p_p2_title, p_p2_tag]], colWidths=[printable_width * 0.80, printable_width * 0.20])
    p2_header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#1A2B4C')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(p2_header_table)
    story.append(Spacer(1, 6))

    # 2. Chart 3: Balance Sheet Composition Stacked Bar
    buf_chart3 = create_balance_sheet_stacked_chart(data['bs_history'])
    img_chart3 = Image(buf_chart3, width=printable_width, height=155)
    story.append(img_chart3)
    story.append(Spacer(1, 6))

    # 3. Chart 4: Cash Flow Waterfall Bar Chart
    buf_chart4 = create_cashflow_waterfall_chart(data['cf_latest'])
    img_chart4 = Image(buf_chart4, width=printable_width, height=140)
    story.append(img_chart4)
    story.append(Spacer(1, 6))

    # 4. Pros & Cons Section + Capital Allocation Badge
    pros_flowables = [Paragraph("<font color='#1E8449'><b>KEY INVESTMENT STRENGTHS (PROS)</b></font>", style_sec_header), Spacer(1, 3)]
    for p_text in data['pros'][:4]:  # Top 4 pros
        pros_flowables.append(Paragraph(f"✔ {p_text}", style_bullet_pro))
        pros_flowables.append(Spacer(1, 2))

    cons_flowables = [Paragraph("<font color='#C0392B'><b>KEY INVESTMENT RISKS (CONS)</b></font>", style_sec_header), Spacer(1, 3)]
    for c_text in data['cons'][:4]:  # Top 4 cons
        cons_flowables.append(Paragraph(f"✖ {c_text}", style_bullet_con))
        cons_flowables.append(Spacer(1, 2))

    half_w = (printable_width - 8) / 2.0
    pros_cons_table = Table([[pros_flowables, cons_flowables]], colWidths=[half_w, half_w])
    pros_cons_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#E8F8F5')),
        ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#FDEDEC')),
        ('BOX', (0, 0), (0, 0), 0.8, colors.HexColor('#27AE60')),
        ('BOX', (1, 0), (1, 0), 0.8, colors.HexColor('#E74C3C')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(pros_cons_table)
    story.append(Spacer(1, 6))

    # 5. Capital Allocation Badge
    badge_p = Paragraph(
        f"CAPITAL ALLOCATION PATTERN: <font color='#ECCC68'><b>{data['cap_alloc'].upper()}</b></font>",
        style_badge
    )
    badge_table = Table([[badge_p]], colWidths=[printable_width])
    badge_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#1A2B4C')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(badge_table)

    # Build document
    doc.build(story, canvasmaker=NumberedCanvas)
    
    # Verify page count
    with open(output_path, 'rb') as f:
        content = f.read()
    page_count = len(re.findall(rb'/Type\s*/Page[^s]', content))
    logger.info(f"Generated tearsheet for '{company_id}' -> {output_path} (Pages: {page_count})")
    
    if page_count != 2:
        logger.warning(f"[OVERFLOW WARNING] '{company_id}' tearsheet generated {page_count} pages instead of 2!")

    return output_path


def main():
    """Test tearsheet generator on 5 companies from different sectors."""
    test_tickers = ['TCS', 'HDFCBANK', 'RELIANCE', 'SUNPHARMA', 'TATASTEEL']
    print("=== TESTING TEARSHEET GENERATION ON 5 SECTOR REPRESENTATIVE COMPANIES ===")
    
    for ticker in test_tickers:
        try:
            pdf_path = generate_tearsheet(ticker)
            with open(pdf_path, 'rb') as f:
                content = f.read()
            pages = len(re.findall(rb'/Type\s*/Page[^s]', content))
            print(f"[OK] {ticker:<10} -> {pdf_path} | Pages: {pages}")
            assert pages == 2, f"Failed page constraint for {ticker}: {pages} pages!"
        except Exception as e:
            print(f"[FAIL] {ticker}: {e}")


if __name__ == "__main__":
    main()
