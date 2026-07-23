"""
src/dashboard/utils/db.py
Shared database query functions with Streamlit caching.
All query functions use @st.cache_data(ttl=600) for a 10-minute cache.
"""

import os
import sqlite3
import pandas as pd
import streamlit as st

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "nifty100.db")


def _get_conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


@st.cache_data(ttl=600)
def get_companies() -> pd.DataFrame:
    """Return all companies with id, company_name."""
    conn = _get_conn()
    df = pd.read_sql("SELECT id, company_name FROM companies ORDER BY company_name", conn)
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_ratios(ticker: str, year: str = None) -> pd.DataFrame:
    """Return financial ratios for a ticker. If year is None, return all years."""
    conn = _get_conn()
    if year:
        df = pd.read_sql(
            "SELECT * FROM financial_ratios WHERE company_id = ? AND year = ?",
            conn, params=(ticker, year)
        )
    else:
        df = pd.read_sql(
            "SELECT * FROM financial_ratios WHERE company_id = ? ORDER BY year",
            conn, params=(ticker,)
        )
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_pl(ticker: str) -> pd.DataFrame:
    """Return full P&L history for a ticker."""
    conn = _get_conn()
    df = pd.read_sql(
        "SELECT * FROM profitandloss WHERE company_id = ? ORDER BY year",
        conn, params=(ticker,)
    )
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_bs(ticker: str) -> pd.DataFrame:
    """Return full Balance Sheet history for a ticker."""
    conn = _get_conn()
    df = pd.read_sql(
        "SELECT * FROM balancesheet WHERE company_id = ? ORDER BY year",
        conn, params=(ticker,)
    )
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_cf(ticker: str) -> pd.DataFrame:
    """Return full Cash Flow history for a ticker."""
    conn = _get_conn()
    df = pd.read_sql(
        "SELECT * FROM cashflow WHERE company_id = ? ORDER BY year",
        conn, params=(ticker,)
    )
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_sectors() -> pd.DataFrame:
    """Return sectors mapping: company_id, broad_sector, sub_sector."""
    conn = _get_conn()
    df = pd.read_sql(
        "SELECT s.company_id, c.company_name, s.broad_sector, s.sub_sector "
        "FROM sectors s JOIN companies c ON s.company_id = c.id",
        conn
    )
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_peers(group_name: str) -> pd.DataFrame:
    """Return companies in a given peer group with their key ratios."""
    conn = _get_conn()
    df = pd.read_sql(
        """
        SELECT pg.company_id, c.company_name, pg.peer_group_name,
               fr.return_on_equity_pct, fr.net_profit_margin_pct,
               fr.debt_to_equity, fr.composite_quality_score
        FROM peer_groups pg
        JOIN companies c ON pg.company_id = c.id
        LEFT JOIN financial_ratios fr ON pg.company_id = fr.company_id AND fr.year = '2024-03'
        WHERE pg.peer_group_name = ?
        """,
        conn, params=(group_name,)
    )
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_valuation(ticker: str) -> pd.DataFrame:
    """Return market cap and valuation multiples for a ticker."""
    conn = _get_conn()
    df = pd.read_sql(
        "SELECT * FROM market_cap WHERE company_id = ? ORDER BY year",
        conn, params=(ticker,)
    )
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_all_ratios_for_year(year: str = "2024-03") -> pd.DataFrame:
    """Return financial ratios for all companies for a given year, joined with sector info."""
    conn = _get_conn()
    df = pd.read_sql(
        """
        SELECT fr.*, c.company_name, s.broad_sector, s.sub_sector
        FROM financial_ratios fr
        JOIN companies c ON fr.company_id = c.id
        LEFT JOIN sectors s ON fr.company_id = s.company_id
        WHERE fr.year = ?
        ORDER BY fr.composite_quality_score DESC
        """,
        conn, params=(year,)
    )
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_pros_cons(ticker: str) -> pd.DataFrame:
    """Return pros and cons for a company."""
    conn = _get_conn()
    df = pd.read_sql(
        "SELECT * FROM prosandcons WHERE company_id = ?",
        conn, params=(ticker,)
    )
    conn.close()
    return df
