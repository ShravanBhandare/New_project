import pytest
import pandas as pd
from src.analytics.screener.engine import winsorise_and_scale, score_de, score_icr

def test_winsorise_and_scale():
    # Test on a simple series of values
    series = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0])
    # Quantiles: P10 = 19.0, P90 = 91.0
    # Capped should be clipped to [19.0, 91.0]
    scaled = winsorise_and_scale(series)
    assert scaled.min() == 0.0
    assert scaled.max() == 100.0
    # Capped value for 50.0 is 50.0. Scaled value should be (50 - 19) / (91 - 19) * 100 = 43.05
    assert abs(scaled.iloc[4] - 43.05) < 0.1

def test_score_de_edge_cases():
    assert score_de(0.0) == 100.0
    assert score_de(0.5) == 85.0
    assert score_de(1.0) == 70.0
    assert score_de(2.0) == 50.0
    assert score_de(5.0) == 0.0
    assert score_de(6.0) == 0.0
    # Interpolated
    assert score_de(0.25) == 92.5
    assert score_de(1.5) == 60.0

def test_score_icr_edge_cases():
    assert score_icr(10.0) == 100.0
    assert score_icr(12.0) == 100.0
    assert score_icr(5.0) == 75.0
    assert score_icr(3.0) == 50.0
    assert score_icr(1.5) == 0.0
    assert score_icr(1.0) == 0.0
    # Interpolated
    assert score_icr(7.5) == 87.5
    assert score_icr(4.0) == 62.5
    assert score_icr(2.25) == 25.0
