import streamlit as st
import os
import pandas as pd
from src.dashboard.utils.db import get_companies

st.set_page_config(layout="wide")

st.title("📄 PDF Reports Repository")
st.markdown("Access pre-generated Company Tearsheets (2-page summaries), Sector Benchmarks, and the Nifty 100 Portfolio Summary report.")

# Folders where reports are generated
TEARSHEET_DIR = "reports/tearsheets"
SECTOR_DIR = "reports/sector"
PORTFOLIO_DIR = "reports/portfolio"

tab1, tab2, tab3 = st.tabs(["📁 Company Tearsheets", "🏢 Sector Benchmark Reports", "📊 Portfolio Summary"])

with tab1:
    st.subheader("Download Company Tearsheets")
    companies_df = get_companies()
    
    if not companies_df.empty:
        col_c, col_d = st.columns([2, 1])
        with col_c:
            selected_option = st.selectbox("Select Ticker", [f"{row['id']} - {row['company_name']}" for idx, row in companies_df.iterrows()])
            ticker = selected_option.split(" - ")[0]
            
            pdf_filename = f"{ticker}_tearsheet.pdf"
            pdf_path = os.path.join(TEARSHEET_DIR, pdf_filename)
            
            # Check if file exists
            if os.path.exists(pdf_path):
                st.success(f"Tearsheet for {ticker} is ready for download.")
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        label=f"📥 Download {ticker} tearsheet (PDF)",
                        data=f,
                        file_name=pdf_filename,
                        mime="application/pdf"
                    )
            else:
                st.info(f"Tearsheet file '{pdf_filename}' not found in reports directory. Run make report to pre-generate tearsheets.")
    else:
        st.error("No companies loaded in the database.")

with tab2:
    st.subheader("Download Sector Benchmark Reports")
    try:
        conn = get_connection()
        sectors = pd.read_sql("SELECT DISTINCT broad_sector FROM sectors", conn)['broad_sector'].tolist()
        conn.close()
    except:
        sectors = []
        
    if sectors:
        selected_sector = st.selectbox("Select Sector", sectors)
        # Sector report filename
        # Sector report files are named: <SECTOR>_report_YYYYMMDD.pdf. Let's list files in the sector folder.
        if os.path.exists(SECTOR_DIR):
            files = os.listdir(SECTOR_DIR)
            matching_files = [f for f in files if selected_sector in f and f.endswith('.pdf')]
            
            if matching_files:
                for f_name in matching_files:
                    f_path = os.path.join(SECTOR_DIR, f_name)
                    st.markdown(f"**Report File:** `{f_name}`")
                    with open(f_path, "rb") as f:
                        st.download_button(
                            label=f"📥 Download {f_name} (PDF)",
                            data=f,
                            file_name=f_name,
                            mime="application/pdf"
                        )
            else:
                st.info(f"No benchmark reports found for sector '{selected_sector}' in {SECTOR_DIR}. Run make report to pre-generate reports.")
        else:
            st.info(f"Sector directory '{SECTOR_DIR}' does not exist.")
    else:
        st.info("No sectors found.")

with tab3:
    st.subheader("Download Portfolio Summary Report")
    st.markdown("Unified portfolio summary containing relative metric aggregates and 3-year direction indicators for all 92 companies.")
    
    if os.path.exists(PORTFOLIO_DIR):
        files = os.listdir(PORTFOLIO_DIR)
        portfolio_files = [f for f in files if f.startswith('portfolio_summary') and f.endswith('.pdf')]
        
        if portfolio_files:
            for f_name in portfolio_files:
                f_path = os.path.join(PORTFOLIO_DIR, f_name)
                st.markdown(f"**Portfolio File:** `{f_name}`")
                with open(f_path, "rb") as f:
                    st.download_button(
                        label=f"📥 Download {f_name} (PDF)",
                        data=f,
                        file_name=f_name,
                        mime="application/pdf"
                    )
        else:
            st.info(f"No portfolio summary reports found in {PORTFOLIO_DIR}. Run make report to pre-generate reports.")
    else:
        st.info(f"Portfolio directory '{PORTFOLIO_DIR}' does not exist.")
