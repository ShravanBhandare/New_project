-- Exploratory Queries for Nifty 100 Ingested Data (Sprint 1)

-- 1. Count of companies per broad sector
SELECT broad_sector, COUNT(*) as company_count
FROM sectors
GROUP BY broad_sector
ORDER BY company_count DESC;

-- 2. Select top 5 companies by paid-up equity capital in the latest available year
SELECT company_id, year, equity_capital
FROM balancesheet
WHERE year = '2024-03'
ORDER BY equity_capital DESC
LIMIT 5;

-- 3. List the 5 most recent document links ingested
SELECT company_id, Year, Annual_Report
FROM documents
ORDER BY Year DESC
LIMIT 5;

-- 4. Compute total revenues and net profits for TCS over all years
SELECT year, sales as revenue, net_profit
FROM profitandloss
WHERE company_id = 'TCS'
ORDER BY year ASC;

-- 5. Calculate average return on equity (ROE) per sector in 2024
SELECT s.broad_sector, ROUND(AVG(f.return_on_equity_pct), 2) as avg_roe
FROM sectors s
JOIN financial_ratios f ON s.company_id = f.company_id
WHERE f.year = '2024-03'
GROUP BY s.broad_sector
ORDER BY avg_roe DESC;

-- 6. Retrieve companies with high debt-to-equity (>2.0) in the latest financial year
SELECT company_id, year, debt_to_equity
FROM financial_ratios
WHERE year = '2024-03' AND debt_to_equity > 2.0
ORDER BY debt_to_equity DESC;

-- 7. Identify companies with limited historical coverage (< 5 years of P&L records)
SELECT company_id, COUNT(year) as record_count
FROM profitandloss
GROUP BY company_id
HAVING record_count < 5
ORDER BY record_count ASC;

-- 8. Find the maximum EPS achieved by any company in the database
SELECT company_id, year, eps
FROM profitandloss
WHERE eps IS NOT NULL
ORDER BY eps DESC
LIMIT 1;

-- 9. Select all companies in the "IT Services" sub-sector and their index weight
SELECT company_id, index_weight_pct
FROM sectors
WHERE sub_sector = 'IT Services'
ORDER BY index_weight_pct DESC;

-- 10. Query the top 5 companies by latest adjusted close price in stock_prices
SELECT company_id, date, adjusted_close
FROM stock_prices
WHERE date = (SELECT MAX(date) FROM stock_prices)
ORDER BY adjusted_close DESC
LIMIT 5;
