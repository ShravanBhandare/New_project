"""
src/reports/portfolio_report.py

Generates the Portfolio Summary PDF (reports/portfolio/portfolio_summary.pdf).
- One page per company in alphabetical order by ticker.
- Displays company metadata, top 6 KPIs with YoY trend indicators (▲ Up, ▼ Down, ▶ Flat),
  historical performance summary, pros/cons bullet points, and capital allocation badge.
- Built using ReportLab and styled for clean 1-page per company PDF output.
"""

import os
import io
import re
import sqlite3
import logging
import pandas as pd
import numpy as np

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)
from reportlab.pdfgen.canvas import Canvas

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "nifty100.db")
PROS_CONS_CSV = os.path.join(os.path.dirname(__file__), "..", "..", "output", "pros_cons_generated.csv")
PORTFOLIO_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "reports", "portfolio")


class PortfolioNumberedCanvas(Canvas):
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
        self.drawString(28.8, 14, "Nifty 100 Financial Analytics | Executive Portfolio Summary")
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(612 - 28.8, 14, page_text)
        self.restoreState()


def get_trend_indicator(curr: float | None, prev: float | None, is_ratio: bool = True) -> tuple[str, str]:
    """
    Returns (trend_symbol, color_hex) based on YoY metric comparison.
    Up arrow ▲ if improved > 2%, Down arrow ▼ if declined > 2%, Flat ▶ within 2%.
    """
    if curr is None or pd.isna(curr) or prev is None or pd.isna(prev):
        return ("▶", "#7F8C8D")
    
    diff = curr - prev
    if is_ratio:
        # Percentage point difference for ROE/ROCE
        if diff > 0.5:
            return ("▲", "#27AE60")
        elif diff < -0.5:
            return ("▼", "#C0392B")
        else:
            return ("▶", "#7F8C8D")
    else:
        # Percentage change for Sales / FCF / MarketCap
        if abs(prev) > 0:
            pct_change = (diff / abs(prev)) * 100
        else:
            pct_change = 0.0
            
        if pct_change > 2.0:
            return ("▲", "#27AE60")
        elif pct_change < -2.0:
            return ("▼", "#C0392B")
        else:
            return ("▶", "#7F8C8D")


def generate_portfolio_summary(output_path: str = None, db_path: str = DB_PATH) -> str:
    """
    Generate the Portfolio Summary PDF with 1 page per company sorted alphabetically.
    """
    if not output_path:
        os.makedirs(PORTFOLIO_DIR, exist_ok=True)
        output_path = os.path.join(PORTFOLIO_DIR, "portfolio_summary.pdf")
    else:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    conn = sqlite3.connect(db_path)
    df_comp = pd.read_sql("SELECT id, company_name FROM companies ORDER BY id ASC", conn)
    
    # Load Pros & Cons
    df_pc = pd.read_csv(PROS_CONS_CSV) if os.path.exists(PROS_CONS_CSV) else pd.DataFrame()

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
    
    style_header_title = ParagraphStyle('PortTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=16, textColor=colors.white, leading=19)
    style_header_sub = ParagraphStyle('PortSub', parent=styles['Normal'], fontName='Helvetica', fontSize=8.5, textColor=colors.HexColor('#CED6E0'), leading=11)
    style_header_tag = ParagraphStyle('PortTag', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, textColor=colors.HexColor('#ECCC68'), alignment=2, leading=13)
    
    style_kpi_label = ParagraphStyle('PortKPILabel', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=7.5, textColor=colors.HexColor('#57606F'), alignment=1, leading=9)
    style_kpi_val = ParagraphStyle('PortKPIVal', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10.5, textColor=colors.HexColor('#1A2B4C'), alignment=1, leading=13)
    
    style_sec_header = ParagraphStyle('PortSecHead', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leading=12)
    style_bullet_pro = ParagraphStyle('PortBulletPro', parent=styles['Normal'], fontName='Helvetica', fontSize=8, textColor=colors.HexColor('#1E8449'), leading=10, wordWrap='CJK')
    style_bullet_con = ParagraphStyle('PortBulletCon', parent=styles['Normal'], fontName='Helvetica', fontSize=8, textColor=colors.HexColor('#C0392B'), leading=10, wordWrap='CJK')
    style_badge = ParagraphStyle('PortBadgeText', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, textColor=colors.white, alignment=1, leading=11)
    
    style_th = ParagraphStyle('PortTableHead', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=7.5, textColor=colors.white, alignment=1, leading=9)
    style_td = ParagraphStyle('PortTableData', parent=styles['Normal'], fontName='Helvetica', fontSize=7.5, textColor=colors.HexColor('#2C3E50'), alignment=1, leading=9)
    style_td_left = ParagraphStyle('PortTableDataLeft', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=7.5, textColor=colors.HexColor('#1A2B4C'), alignment=0, leading=9)

    story = []
    processed_companies = 0

    for idx, row in df_comp.iterrows():
        cid = row['id']
        name = row['company_name']
        
        # Sector Info
        df_sec = pd.read_sql("SELECT broad_sector, sub_sector FROM sectors WHERE company_id = ?", conn, params=(cid,))
        b_sec = df_sec.iloc[0]['broad_sector'] if not df_sec.empty else 'N/A'
        s_sec = df_sec.iloc[0]['sub_sector'] if not df_sec.empty else 'N/A'
        
        # Market Cap & Valuation (2024)
        df_mc = pd.read_sql("SELECT market_cap_crore, pe_ratio, pb_ratio FROM market_cap WHERE company_id = ? AND year = 2024", conn, params=(cid,))
        mcap = df_mc.iloc[0]['market_cap_crore'] if not df_mc.empty and pd.notna(df_mc.iloc[0]['market_cap_crore']) else None
        pe = df_mc.iloc[0]['pe_ratio'] if not df_mc.empty and pd.notna(df_mc.iloc[0]['pe_ratio']) else None
        
        # Ratios (2024-03 vs 2023-03)
        df_r24 = pd.read_sql("SELECT return_on_equity_pct, return_on_capital_employed_pct, debt_to_equity, free_cash_flow_cr, capital_allocation_pattern, sales_cagr_5yr FROM financial_ratios WHERE company_id = ? AND year = '2024-03'", conn, params=(cid,))
        df_r23 = pd.read_sql("SELECT return_on_equity_pct, return_on_capital_employed_pct, debt_to_equity, free_cash_flow_cr FROM financial_ratios WHERE company_id = ? AND year = '2023-03'", conn, params=(cid,))
        
        roe_24 = df_r24.iloc[0]['return_on_equity_pct'] if not df_r24.empty else None
        roe_23 = df_r23.iloc[0]['return_on_equity_pct'] if not df_r23.empty else None
        
        roce_24 = df_r24.iloc[0]['return_on_capital_employed_pct'] if not df_r24.empty else None
        roce_23 = df_r23.iloc[0]['return_on_capital_employed_pct'] if not df_r23.empty else None
        
        de_24 = df_r24.iloc[0]['debt_to_equity'] if not df_r24.empty else None
        de_23 = df_r23.iloc[0]['debt_to_equity'] if not df_r23.empty else None
        
        fcf_24 = df_r24.iloc[0]['free_cash_flow_cr'] if not df_r24.empty else None
        fcf_23 = df_r23.iloc[0]['free_cash_flow_cr'] if not df_r23.empty else None
        
        cap_alloc = df_r24.iloc[0]['capital_allocation_pattern'] if not df_r24.empty else 'N/A'
        rev_cagr = df_r24.iloc[0]['sales_cagr_5yr'] if not df_r24.empty else None
        
        # Compute Trend Indicators
        sym_roe, col_roe = get_trend_indicator(roe_24, roe_23, is_ratio=True)
        sym_roce, col_roce = get_trend_indicator(roce_24, roce_23, is_ratio=True)
        sym_de, col_de = get_trend_indicator(de_23, de_24, is_ratio=True)  # Inverted for debt
        sym_fcf, col_fcf = get_trend_indicator(fcf_24, fcf_23, is_ratio=False)

        # 1. Navy Header Bar
        p_title = Paragraph(f"<b>{name}</b> <font color='#70A1FF'>({cid})</font>", style_header_title)
        p_sec = Paragraph(f"Broad Sector: <b>{b_sec}</b> &nbsp;|&nbsp; Sub-Sector: <b>{s_sec}</b>", style_header_sub)
        p_tag = Paragraph("PORTFOLIO SUMMARY<br/><font color='#CED6E0' size=8>Nifty 100 Analytics</font>", style_header_tag)
        
        header_table = Table([[p_title, p_tag], [p_sec, '']], colWidths=[printable_width * 0.72, printable_width * 0.28])
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
        story.append(Spacer(1, 10))

        # 2. 6 KPI Cards with Trend Indicators
        mcap_str = f"₹{mcap:,.0f} Cr" if mcap is not None and pd.notna(mcap) else "N/A"
        pe_str = f"{pe:.1f}x" if pe is not None and pd.notna(pe) else "N/A"
        roe_str = f"{roe_24:.1f}% <font color='{col_roe}'><b>{sym_roe}</b></font>" if roe_24 is not None and pd.notna(roe_24) else "N/A"
        cagr_str = f"{rev_cagr:.1f}%" if rev_cagr is not None and pd.notna(rev_cagr) else "N/A"
        
        if b_sec == 'Financials':
            de_str = "Suppressed"
        else:
            de_str = f"{de_24:.2f} <font color='{col_de}'><b>{sym_de}</b></font>" if de_24 is not None and pd.notna(de_24) and de_24 > 0 else "0.00 (Debt Free)"
            
        fcf_str = f"₹{fcf_24:,.0f} Cr <font color='{col_fcf}'><b>{sym_fcf}</b></font>" if fcf_24 is not None and pd.notna(fcf_24) else "N/A"

        tiles_data = [
            [
                [Paragraph("MARKET CAP", style_kpi_label), Paragraph(mcap_str, style_kpi_val)],
                [Paragraph("P/E RATIO", style_kpi_label), Paragraph(pe_str, style_kpi_val)],
                [Paragraph("RETURN ON EQUITY", style_kpi_label), Paragraph(roe_str, style_kpi_val)]
            ],
            [
                [Paragraph("5Y REVENUE CAGR", style_kpi_label), Paragraph(cagr_str, style_kpi_val)],
                [Paragraph("DEBT TO EQUITY", style_kpi_label), Paragraph(de_str, style_kpi_val)],
                [Paragraph("FREE CASH FLOW", style_kpi_label), Paragraph(fcf_str, style_kpi_val)]
            ]
        ]

        col_w = printable_width / 3.0
        kpi_table = Table(tiles_data, colWidths=[col_w, col_w, col_w])
        kpi_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8F9FA')),
            ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor('#1A2B4C')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#DFE4EA')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(kpi_table)
        story.append(Spacer(1, 12))

        # 3. 5-Year Historical Performance Summary Table
        df_pl_hist = pd.read_sql("SELECT year, sales, net_profit FROM profitandloss WHERE company_id = ? AND year LIKE '%-03' ORDER BY year DESC LIMIT 5", conn, params=(cid,))
        df_fr_hist = pd.read_sql("SELECT year, return_on_equity_pct, return_on_capital_employed_pct, debt_to_equity, free_cash_flow_cr FROM financial_ratios WHERE company_id = ? AND year LIKE '%-03' ORDER BY year DESC LIMIT 5", conn, params=(cid,))
        
        hist_table_data = [[
            Paragraph("Year", style_th),
            Paragraph("Sales (₹ Cr)", style_th),
            Paragraph("Net Profit (₹ Cr)", style_th),
            Paragraph("ROE (%)", style_th),
            Paragraph("ROCE (%)", style_th),
            Paragraph("D/E Ratio", style_th),
            Paragraph("FCF (₹ Cr)", style_th)
        ]]
        
        if not df_pl_hist.empty:
            df_merged_hist = pd.merge(df_pl_hist, df_fr_hist, on='year', how='left').sort_values('year', ascending=True)
            for _, hrow in df_merged_hist.iterrows():
                yr_lbl = str(hrow['year']).replace('-03', '')
                h_sales = f"₹{hrow['sales']:,.0f}" if pd.notna(hrow['sales']) else "N/A"
                h_profit = f"₹{hrow['net_profit']:,.0f}" if pd.notna(hrow['net_profit']) else "N/A"
                h_roe = f"{hrow['return_on_equity_pct']:.1f}%" if pd.notna(hrow['return_on_equity_pct']) else "N/A"
                h_roce = f"{hrow['return_on_capital_employed_pct']:.1f}%" if pd.notna(hrow['return_on_capital_employed_pct']) else "N/A"
                h_de = "Suppressed" if b_sec == 'Financials' else (f"{hrow['debt_to_equity']:.2f}" if pd.notna(hrow['debt_to_equity']) else "N/A")
                h_fcf = f"₹{hrow['free_cash_flow_cr']:,.0f}" if pd.notna(hrow['free_cash_flow_cr']) else "N/A"
                
                hist_table_data.append([
                    Paragraph(f"<b>FY{yr_lbl}</b>", style_td_left),
                    Paragraph(h_sales, style_td),
                    Paragraph(h_profit, style_td),
                    Paragraph(h_roe, style_td),
                    Paragraph(h_roce, style_td),
                    Paragraph(h_de, style_td),
                    Paragraph(h_fcf, style_td)
                ])

        h_col_w = printable_width / 7.0
        hist_table = Table(hist_table_data, colWidths=[h_col_w]*7)
        hist_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1A2B4C')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#DFE4EA')),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(hist_table)
        story.append(Spacer(1, 12))

        # 4. Pros and Cons Section
        pros = []
        cons = []
        if not df_pc.empty:
            sub_pc = df_pc[df_pc['company_id'] == cid]
            pros = sub_pc[sub_pc['type'] == 'pro']['text'].tolist()
            cons = sub_pc[sub_pc['type'] == 'con']['text'].tolist()
            
        if not pros:
            pros = ["Demonstrates strong market positioning and established distribution."]
        if not cons:
            cons = ["Monitored for broad sector economic cycles and input cost pressures."]

        pros_flowables = [Paragraph("<font color='#1E8449'><b>KEY INVESTMENT STRENGTHS (PROS)</b></font>", style_sec_header), Spacer(1, 4)]
        for p_txt in pros[:4]:
            pros_flowables.append(Paragraph(f"✔ {p_txt}", style_bullet_pro))
            pros_flowables.append(Spacer(1, 3))

        cons_flowables = [Paragraph("<font color='#C0392B'><b>KEY INVESTMENT RISKS (CONS)</b></font>", style_sec_header), Spacer(1, 4)]
        for c_txt in cons[:4]:
            cons_flowables.append(Paragraph(f"✖ {c_txt}", style_bullet_con))
            cons_flowables.append(Spacer(1, 3))

        half_w = (printable_width - 8) / 2.0
        pros_cons_table = Table([[pros_flowables, cons_flowables]], colWidths=[half_w, half_w])
        pros_cons_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#E8F8F5')),
            ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#FDEDEC')),
            ('BOX', (0, 0), (0, 0), 0.8, colors.HexColor('#27AE60')),
            ('BOX', (1, 0), (1, 0), 0.8, colors.HexColor('#E74C3C')),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(pros_cons_table)
        story.append(Spacer(1, 10))

        # 5. Capital Allocation Badge
        badge_p = Paragraph(
            f"CAPITAL ALLOCATION PATTERN: <font color='#ECCC68'><b>{str(cap_alloc).upper()}</b></font>",
            style_badge
        )
        badge_table = Table([[badge_p]], colWidths=[printable_width])
        badge_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#1A2B4C')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(badge_table)

        processed_companies += 1
        # Page break after every company except the last
        if idx < len(df_comp) - 1:
            story.append(PageBreak())

    conn.close()

    doc.build(story, canvasmaker=PortfolioNumberedCanvas)
    
    with open(output_path, 'rb') as f:
        content = f.read()
    page_count = len(re.findall(rb'/Type\s*/Page[^s]', content))
    logger.info(f"Generated Portfolio Summary PDF for {processed_companies} companies -> {output_path} (Pages: {page_count})")
    
    return output_path


if __name__ == "__main__":
    generate_portfolio_summary()
