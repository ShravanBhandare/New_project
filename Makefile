.PHONY: load ratios cagr cashflow test clean

load:
	.\.venv\Scripts\python.exe -m src.etl.loader

ratios:
	.\.venv\Scripts\python.exe -m src.analytics.ratios

cagr:
	.\.venv\Scripts\python.exe -m src.analytics.cagr

cashflow:
	.\.venv\Scripts\python.exe -m src.analytics.cashflow_kpis

test:
	.\.venv\Scripts\pytest --html=reports/pytest_report.html --self-contained-html

clean:
	powershell -Command "Remove-Item -Recurse -Force -ErrorAction SilentlyContinue .\.pytest_cache, ./**/__pycache__, ./data/nifty100.db, ./load_audit.csv, ./validation_failures.csv, ./reports"
