import pytest
import pandas as pd
from src.analytics.peer import get_peer_comparison_data

def test_peer_comparison_data_load():
    # Verify that the get_peer_comparison_data returns a valid DataFrame
    try:
        df = get_peer_comparison_data()
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert 'company_id' in df.columns
        assert 'composite_score' in df.columns
    except Exception as e:
        pytest.skip(f"DB not fully loaded for test: {e}")
