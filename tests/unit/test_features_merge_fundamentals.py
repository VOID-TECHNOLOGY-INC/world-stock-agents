import pandas as pd

from src.scoring.features import merge_fundamentals


def test_merge_fundamentals_overwrites_defaults():
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
        }
    )

    out = merge_fundamentals(features_df, fundamentals_df)
    row = out.iloc[0]
    assert abs(row["fundamental_roic"] - 0.2) < 1e-9
    assert abs(row["fundamental_fcf_margin"] - 0.1) < 1e-9


