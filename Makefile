.PHONY: load ratios clustering report test api dashboard clean

# Default: runs everything to load, compute, cluster and generate all reports
all: load ratios clustering report test

load:
	.\.venv\Scripts\python.exe -m src.etl.loader

ratios:
	.\.venv\Scripts\python.exe -m src.analytics.populate_ratios

clustering:
	.\.venv\Scripts\python.exe -m src.analytics.clustering

report:
	.\.venv\Scripts\python.exe -m src.reports.generate_all_reports

test:
	.\.venv\Scripts\pytest --html=reports/pytest_report.html --self-contained-html

api:
	.\.venv\Scripts\python.exe -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

dashboard:
	.\.venv\Scripts\streamlit run src.dashboard.app

clean:
	powershell -Command "Remove-Item -Recurse -Force -ErrorAction SilentlyContinue .\.pytest_cache, ./**/__pycache__"
