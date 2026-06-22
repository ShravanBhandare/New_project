import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from typing import List

# Custom color scheme for premium styling
COLOR_PRIMARY = "#1f77b4" # Navy blue
COLOR_SECONDARY = "#ff7f0e" # Vibrant orange
COLOR_ACCENT = "#2ca02c" # Green
COLOR_DARK = "#121212" # Glassmorphic dark background
COLOR_LIGHT = "#f5f7fa"

def plot_financial_trend(pl_df: pd.DataFrame) -> go.Figure:
    """Plotly bar chart of Revenue and Net Profit."""
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=pl_df['year'],
        y=pl_df['sales'],
        name='Sales (Revenue)',
        marker_color=COLOR_PRIMARY
    ))
    
    fig.add_trace(go.Bar(
        x=pl_df['year'],
        y=pl_df['net_profit'],
        name='Net Profit (PAT)',
        marker_color=COLOR_SECONDARY
    ))
    
    fig.update_layout(
        title="Revenue & Net Profit Trend (Cr)",
        barmode='group',
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font_color='#888888',
        margin=dict(l=40, r=40, t=40, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

def plot_balance_sheet(bs_df: pd.DataFrame) -> go.Figure:
    """Stacked bar chart of Balance Sheet Liabilities composition."""
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=bs_df['year'],
        y=bs_df['equity_capital'],
        name='Equity Capital',
        marker_color='#1f77b4'
    ))
    
    fig.add_trace(go.Bar(
        x=bs_df['year'],
        y=bs_df['reserves'].fillna(0.0),
        name='Reserves & Surplus',
        marker_color='#aec7e8'
    ))
    
    fig.add_trace(go.Bar(
        x=bs_df['year'],
        y=bs_df['borrowings'].fillna(0.0),
        name='Borrowings (Debt)',
        marker_color='#ff7f0e'
    ))
    
    fig.add_trace(go.Bar(
        x=bs_df['year'],
        y=bs_df['other_liabilities'].fillna(0.0),
        name='Other Liabilities',
        marker_color='#ffbb78'
    ))
    
    fig.update_layout(
        title="Liabilities Composition (Cr)",
        barmode='stack',
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font_color='#888888',
        margin=dict(l=40, r=40, t=40, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

def plot_cash_flows(cf_df: pd.DataFrame) -> go.Figure:
    """Grouped bar chart of Operating, Investing, and Financing Cash Flows."""
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=cf_df['year'],
        y=cf_df['operating_activity'].fillna(0.0),
        name='CFO (Operations)',
        marker_color=COLOR_ACCENT
    ))
    
    fig.add_trace(go.Bar(
        x=cf_df['year'],
        y=cf_df['investing_activity'].fillna(0.0),
        name='CFI (Investing)',
        marker_color='#d62728'
    ))
    
    fig.add_trace(go.Bar(
        x=cf_df['year'],
        y=cf_df['financing_activity'].fillna(0.0),
        name='CFF (Financing)',
        marker_color='#9467bd'
    ))
    
    fig.update_layout(
        title="Cash Flow Activities (Cr)",
        barmode='group',
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font_color='#888888',
        margin=dict(l=40, r=40, t=40, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

def plot_radar_plotly(labels: List[str], values: List[float], comp_id: str, group_avg: List[float]) -> go.Figure:
    """Interactive Plotly Radar Chart comparing company vs peer average."""
    fig = go.Figure()
    
    fig.add_trace(go.Scatterpolar(
        r=values + [values[0]],
        theta=labels + [labels[0]],
        fill='toself',
        name=comp_id,
        line_color=COLOR_PRIMARY
    ))
    
    fig.add_trace(go.Scatterpolar(
        r=group_avg + [group_avg[0]],
        theta=labels + [labels[0]],
        fill='toself',
        name='Group Avg (50%)',
        line_color=COLOR_SECONDARY,
        fillcolor='rgba(255, 127, 14, 0.05)'
    ))
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 1.0],
                tickformat='.0%'
            )
        ),
        paper_bgcolor='rgba(0,0,0,0)',
        font_color='#888888',
        margin=dict(l=40, r=40, t=40, b=40)
    )
    return fig

def plot_sector_donut(labels: List[str], values: List[float]) -> go.Figure:
    """Donut chart showing sector weights or distribution."""
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=.4,
        marker_colors=px.colors.qualitative.Plotly
    )])
    
    fig.update_layout(
        title="Sector Distribution of Nifty 100",
        paper_bgcolor='rgba(0,0,0,0)',
        font_color='#888888',
        margin=dict(l=40, r=40, t=40, b=40)
    )
    return fig
