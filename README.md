# Nifty 100 Ingestion & ETL Ingest Engine (Sprint 1)

A fundamental data ingestion and normalization ETL (Extract, Transform, Load) pipeline for the Nifty 100 corporate financial statements. The engine loads 12 raw Excel workbooks (7 core financial statements and 5 supplementary directories), standardizes dates and tickers, runs 16 data quality rules, and loads the parsed data into a structured SQLite database.

---

## Sprint 1 Capabilities & Design

1. **L1: Raw Ingestion** - Accesses and reads corporate balance sheets, profit & loss statements, cash flow statements, and metadata files.
2. **L2: Normalization & ETL** - Standardizes ticker symbols to uppercase, parses diverse dates (e.g. `Mar-23`, `Mar-24`) to ISO `YYYY-MM` formats, and cleans string values into clean numbers.
3. **L3: Data Quality (DQ) Validation** - Enforces 16 validation rules (e.g., assets = liabilities check, tax rate validations, URL checks) and logs failures to `validation_failures.csv`.
4. **L4: Persistent Database** - Deploys a schema definition in SQLite (`src/etl/schema.sql`) enforcing unique primary keys, indexes, and constraints.

---

## Directory Map

```
D:\Nifty100
├── config/                  # Logging and environment configuration templates
│   ├── .env.template        # Base template for environment variables
│   └── logging_config.yaml  # Configures python logger outputs
├── data/                    # Storage folder
│   ├── raw/                 # 7 Core Excel sheets
│   └── supporting/          # 5 Supplementary Excel sheets
├── src/                     # Source Code
│   └── etl/                 # Loader scripts, normalizers, schemas, and validators
├── tests/                   # Ingestion unit tests
│   ├── dq/                  # Data quality rule verifications
│   └── etl/                 # Normalizer and loader tests
├── Makefile                 # Ingestion automation commands
└── README.md                # System documentation
```

---

## Installation & Setup

1. **Prerequisites**: Python 3.11+ must be installed.
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

* **Load and Validate Data**: Ingests, normalizes, and loads Excel files into the SQLite database.
  ```powershell
  make load
  ```
* **Execute Test Suite**: Runs all unit tests verifying ETL, normalizers, and DQ rules.
  ```powershell
  make test
  ```
* **Clean Ingestion Outputs**: Resets the SQLite database and deletes cached PyTest reports and audit logs.
  ```powershell
  make clean
  ```
