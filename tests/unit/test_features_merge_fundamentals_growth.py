import pandas as pd

from src.scoring.features import merge_fundamentals


def test_merge_fundamentals_adds_growth_columns():
    features_df = pd.DataFrame(
        {
            "ticker": ["A"],
            "name": ["A"],
            "fundamental_roic": [0.5],
            "fundamental_fcf_margin": [0.5],
        }
    )
    fundamentals_df = pd.DataFrame(
        {
            "ticker": ["A"],
            "roic": [0.2],
            "fcf_margin": [0.1],
            "revenue_cagr": [0.3],
            "eps_growth": [0.4],
        }
    )

    out = merge_fundamentals(features_df, fundamentals_df)
    row = out.iloc[0]
    assert abs(row["fundamental_roic"] - 0.2) < 1e-9
    assert abs(row["fundamental_fcf_margin"] - 0.1) < 1e-9
    assert abs(row["growth_revenue_cagr"] - 0.3) < 1e-9
    assert abs(row["growth_eps_growth"] - 0.4) < 1e-9


