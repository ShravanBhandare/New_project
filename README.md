# Nifty 100 Financial Intelligence Platform

An institutional-grade fundamental analysis and intelligence platform built in Python. The platform ingests 10-13 years of annual reports and financial statements for the Nifty 100 constituents, processes 50+ key performance indicators (KPIs), performs machine learning clustering and sector outlier detection, generates automated PDF tearsheets/sector reports, and exposes a fully responsive Streamlit dashboard and FastAPI REST API.

---

## 7-Layer Architecture & System Design

The project is structured according to a strict 7-layer decoupled design pattern:
1. **L1: Raw Ingestion Layer** - Loads historical raw financial spreadsheets (`balancesheet.xlsx`, `profitandloss.xlsx`, `cashflow.xlsx`, etc.) using Pandas and Openpyxl.
2. **L2: Normalisation & ETL Layer** - Standardizes ticker symbols to uppercase, normalizes varied year/month patterns into `YYYY-MM` ISO formats, and sanitizes numeric strings.
3. **L3: Persistent Storage Layer** - Enforces schemas with SQLite table definitions, foreign keys, and unique indexes to store all raw data and calculations.
4. **L4: Analytics Engine Layer** - Dynamically calculates profitability, liquidity, solvency, leverage, multi-year CAGR metrics, and peer group percentile ranks.
5. **L5: Intelligence & NLP Layer** - Conducts KMeans clustering (5 clusters) to profile companies, detects sector-wise Z-score outliers, and scores qualitative pros/cons sentiment using VADER.
6. **L6: Reporting Layer** - Automatically compiles print-ready, multi-page ReportLab PDF report tearsheets, sector benchmark digests, and index portfolio books.
7. **L7: Interface Layer** - Launches an 8-page Streamlit analytical dashboard and a 16-endpoint FastAPI REST API with Swagger documentation.

---

## Directory Map

```
D:\Nifty100
├── config/                  # Configuration files (YAML, configurations)
├── data/                    # SQLite database, raw Excel files and supporting sheets
│   ├── raw/                 # 7 Core Excel sheets
│   └── supporting/          # 5 Supplementary Excel sheets
├── output/                  # Raw Excel screener exports and intermediate CSV files
├── reports/                 # Print-ready PDFs and visual assets
│   ├── sectors/             # 10 Sector reports
│   ├── tearsheets/          # 92 constituents two-page tearsheets
│   └── radar_charts/        # Constituent peer comparison radar plots
├── src/                     # Source Code
│   ├── analytics/           # KPI calculations, peer rankings, and KMeans clustering
│   ├── api/                 # FastAPI server and routers
│   ├── dashboard/           # Streamlit app and Plotly chart configurations
│   ├── etl/                 # Loader scripts, schemas, and validators
│   ├── nlp/                 # Qualitative parsing and sentiment scorer
│   └── reports/             # ReportLab PDF compile pipelines
├── tests/                   # 60 pytest unit and integration test suite
├── Makefile                 # Automation task commands
└── README.md                # General system documentation
```

---

## Installation & Setup

1. **Prerequisites**: Python 3.11+ must be installed on your system.
2. **Create Virtual Environment**:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\activate
   ```
3. **Install Dependencies**:
   ```powershell
   pip install -r requirements.txt
   ```

---

## How to Run (Makefile Targets)

This project features a `Makefile` automating the execution of the entire pipeline:

* **Load and Validate Data**: Ingests, normalizes, and loads Excel files into the SQLite database.
  ```powershell
  make load
  ```
* **Compute Ratios**: Runs the KPI calculator and populates ratios.
  ```powershell
  make ratios
  ```
* **Run Unsupervised Clustering**: Executes KMeans (5 clusters), Z-score outlier filters, and correlation matrices.
  ```powershell
  make clustering
  ```
* **Generate PDF Reports**: Builds all 92 tearsheets, 10 sector reports, and the main portfolio book.
  ```powershell
  make report
  ```
* **Execute Test Suite**: Runs the 60 pytest test cases verifying ETL, KPIs, API routes, and reports.
  ```powershell
  make test
  ```
* **Host REST API**: Starts the FastAPI development server on port 8000. Serves Swagger docs at `http://127.0.0.1:8000/`.
  ```powershell
  make api
  ```
* **Launch streamilt Dashboard**: Opens the Streamlit interactive dashboard on port 8501.
  ```powershell
  make dashboard
  ```

---

## Acceptance Criteria & Verifications
- **Data Integrity**: 16 Data Quality rules automatically filter and report data issues to `validation_failures.csv`.
- **Deduplication**: Handles duplicate constituent rows by keeping the latest entry, ensuring SQLite PK validity.
- **CAGR Decision Table**: Implements special flags for turnaround cases, loss-making base years, and negative growth.
- **Zero-Interest Exemptions**: substitutes infinite interest coverage ratios with `999.0` (displayed as `Debt Free`).
