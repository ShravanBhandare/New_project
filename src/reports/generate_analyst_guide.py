import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def generate_analyst_guide():
    pdf_path = "reports/analyst_guide.pdf"
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
    
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        leftMargin=54, rightMargin=54,
        topMargin=54, bottomMargin=54
    )
    
    styles = getSampleStyleSheet()
    
    # Custom Palette
    color_primary = colors.HexColor('#113264')
    color_secondary = colors.HexColor('#58a6ff')
    color_neutral_dark = colors.HexColor('#0d1117')
    color_border = colors.HexColor('#d0d7de')
    
    title_style = ParagraphStyle(
        'GuideTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=24,
        textColor=color_primary,
        spaceAfter=10,
        alignment=1 # Centered
    )
    
    subtitle_style = ParagraphStyle(
        'GuideSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        textColor=colors.HexColor('#57606a'),
        spaceAfter=30,
        alignment=1
    )
    
    h1_style = ParagraphStyle(
        'GuideH1',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=16,
        textColor=color_primary,
        spaceBefore=18,
        spaceAfter=8,
        keepWithNext=True
    )
    
    h2_style = ParagraphStyle(
        'GuideH2',
        parent=styles['Heading3'],
        fontName='Helvetica-Bold',
        fontSize=12,
        textColor=colors.HexColor('#24292f'),
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'GuideBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=color_neutral_dark,
        spaceAfter=8
    )
    
    bullet_style = ParagraphStyle(
        'GuideBullet',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13,
        leftIndent=20,
        firstLineIndent=-10,
        spaceAfter=4
    )
    
    code_style = ParagraphStyle(
        'GuideCode',
        parent=styles['Code'],
        fontName='Courier',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#cf222e'),
        backColor=colors.HexColor('#f6f8fa'),
        borderColor=color_border,
        borderWidth=0.5,
        borderPadding=6,
        spaceAfter=8
    )

    story = []
    
    # ================= PAGE 1 =================
    story.append(Spacer(1, 40))
    story.append(Paragraph("Nifty 100 Financial Intelligence Platform", title_style))
    story.append(Paragraph("Institutional Fundamental Analyst Guide", subtitle_style))
    story.append(Spacer(1, 20))
    
    story.append(Paragraph("1. Introduction & Architecture", h1_style))
    story.append(Paragraph(
        "Welcome to the Nifty 100 Financial Intelligence Platform Analyst Guide. This document serves "
        "as the core operational handbook for financial analysts consuming the API endpoints, "
        "inspecting the Streamlit dashboard, or downloading auto-compiled report books.",
        body_style
    ))
    story.append(Paragraph(
        "The platform operates on a <b>7-Layer Decoupled Architecture</b> designed to separate concerns, "
        "enforce strict database validations, and run performant financial computations. Data flows "
        "sequentially from L1 (Raw Excel Ingestion) to L3 (SQLite Database), L4 (KPI Ratio Engine), "
        "L5 (KMeans and NLP Analytics), L6 (ReportLab PDF Generation), and finally L7 (Interface Layer).",
        body_style
    ))
    story.append(Paragraph("2. Operational Quickstart", h1_style))
    story.append(Paragraph(
        "Analysts can execute tasks in the workspace using the following commands defined in the project Makefile:",
        body_style
    ))
    
    story.append(Paragraph("<b>make load</b> - Ingest raw data sheets and run 16 DQ rules.", bullet_style))
    story.append(Paragraph("<b>make ratios</b> - Populates computed ratios in the database.", bullet_style))
    story.append(Paragraph("<b>make clustering</b> - Fit KMeans, compute Z-scores and Pearson matrices.", bullet_style))
    story.append(Paragraph("<b>make report</b> - Rebuild all 92 tearsheets and sector PDFs.", bullet_style))
    story.append(Paragraph("<b>make test</b> - Execute the pytest suite (60 test cases).", bullet_style))
    story.append(Paragraph("<b>make api</b> - Start the FastAPI REST server on port 8000.", bullet_style))
    story.append(Paragraph("<b>make dashboard</b> - Run Streamlit app on port 8501.", bullet_style))
    
    story.append(PageBreak())
    
    # ================= PAGE 2 =================
    story.append(Paragraph("3. Ratio Engine Formulas & Specifications", h1_style))
    story.append(Paragraph(
        "The L4 analytics layer processes 50+ financial ratios. The core definitions are:",
        body_style
    ))
    
    story.append(Paragraph("3.1 Profitability & Return Ratios", h2_style))
    story.append(Paragraph(
        "<b>Return on Equity (ROE):</b> Net Profit / Total Equity (Equity Share Capital + Reserves). "
        "If equity is negative, ROE returns 0.0 to prevent misleading math.",
        bullet_style
    ))
    story.append(Paragraph(
        "<b>Return on Capital Employed (ROCE):</b> EBIT / Capital Employed. Capital Employed is defined "
        "as Equity + Reserves + Long-term Borrowings.",
        bullet_style
    ))
    story.append(Paragraph(
        "<b>Operating Profit Margin (OPM):</b> Operating Profit / Revenue (Sales). Missing bank operating margins "
        "are handled gracefully.",
        bullet_style
    ))
    
    story.append(Paragraph("3.2 Solvency & Leverage Ratios", h2_style))
    story.append(Paragraph(
        "<b>Debt-to-Equity (D/E):</b> Borrowings / Total Equity. Enforces sector exclusions (e.g. D/E for banks/NBFCs "
        "is displayed with caution flags).",
        bullet_style
    ))
    story.append(Paragraph(
        "<b>Interest Coverage Ratio (ICR):</b> (Operating Profit + Other Income) / Interest Expense. "
        "When Interest is zero, the engine substitutes a score of <b>999.0</b>, which displays as 'Debt Free' in report summaries.",
        bullet_style
    ))
    
    story.append(Paragraph("3.3 Cash Flow KPI Metrics", h2_style))
    story.append(Paragraph(
        "<b>CFO Quality Score:</b> Average CFO / PAT over 5 years. Ratios > 1.0 indicate 'High Quality Earnings'. "
        "Ratios < 0.5 flag 'Accrual Risk' (cash conversion lag).",
        bullet_style
    ))
    story.append(Paragraph(
        "<b>CapEx Intensity:</b> CapEx / Sales. Scaled as 'Asset-Light' (<3%) or 'Capital-Intensive' (>8%).",
        bullet_style
    ))
    story.append(Paragraph(
        "<b>FCF Conversion:</b> Free Cash Flow (CFO + CFI) / EBITDA.",
        bullet_style
    ))
    
    story.append(PageBreak())
    
    # ================= PAGE 3 =================
    story.append(Paragraph("4. Unsupervised Clustering & Outliers", h1_style))
    story.append(Paragraph(
        "The L5 intelligence layer segments the constituent universe to uncover statistical groupings "
        "without lookahead bias.",
        body_style
    ))
    
    story.append(Paragraph("4.1 KMeans Cluster Profiles (K=5)", h2_style))
    story.append(Paragraph(
        "Using 5 standardized metrics (ROE, D/E, Revenue CAGR 5yr, FCF CAGR 5yr, OPM), companies are grouped into:",
        body_style
    ))
    
    story.append(Paragraph(
        "<b>1. High-Quality Growth Compounder:</b> Low debt, high ROE (>18%), and strong double-digit growth.",
        bullet_style
    ))
    story.append(Paragraph(
        "<b>2. Sturdy Cash Cows:</b> Highly profitable, asset-light, stable cash generation, low growth.",
        bullet_style
    ))
    story.append(Paragraph(
        "<b>3. Leveraged / High Debt:</b> Debt-loaded companies, typical of capital-intensive utilities or NBFCs.",
        bullet_style
    ))
    story.append(Paragraph(
        "<b>4. Steady Performers:</b> Near-average ROE, reasonable growth, standard leverage.",
        bullet_style
    ))
    story.append(Paragraph(
        "<b>5. Underperformers / Cyclical Lows:</b> Muted growth, low ROE, or loss-making operations.",
        bullet_style
    ))
    
    story.append(Paragraph("4.2 Sector Outlier Detection (Z-Score)", h2_style))
    story.append(Paragraph(
        "Outliers are flagged when a constituent company's key metrics deviate from its sector median "
        "by more than 3.0 standard deviations (|Z| > 3.0). This isolates statistical exceptions "
        "(e.g., extremely high leverage or exceptional ROE) for follow-up fundamental audit.",
        body_style
    ))
    
    story.append(Paragraph("5. REST API Usage", h1_style))
    story.append(Paragraph(
        "FastAPI handles the API microservices. Start it using 'make api' and access the swagger page at http://localhost:8000/.",
        body_style
    ))
    story.append(Paragraph("Common routes include:", body_style))
    story.append(Paragraph("<b>GET /api/v1/companies</b> - List constituents.", code_style))
    story.append(Paragraph("<b>GET /api/v1/companies/{ticker}/ratios</b> - Fetch computed ratios history.", code_style))
    story.append(Paragraph("<b>GET /api/v1/screener?preset=quality_compounder</b> - Run preset screen filter.", code_style))
    story.append(Paragraph("<b>GET /api/v1/reports/tearsheet/{ticker}</b> - Download the tearsheet PDF.", code_style))
    
    doc.build(story)
    print("Analyst Guide PDF generated successfully.")

if __name__ == "__main__":
    generate_analyst_guide()
