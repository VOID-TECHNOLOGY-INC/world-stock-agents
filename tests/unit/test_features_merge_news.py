from datetime import date
import pandas as pd

from src.scoring.features import merge_news_signal


def test_merge_news_signal_scales_counts_to_zero_one():
    features_df = pd.DataFrame(
        {
            "ticker": ["A", "B"],
            "name": ["A", "B"],
            "news_signal": [0.5, 0.5],
        }
    )

    news_items = [
        {"ticker": "A", "title": "t1", "url": "u1", "date": str(date(2025, 8, 1))},
        {"ticker": "A", "title": "t2", "url": "u2", "date": str(date(2025, 8, 2))},
        {"ticker": "B", "title": "t3", "url": "u3", "date": str(date(2025, 8, 1))},
    ]

    out = merge_news_signal(features_df, news_items)
    # A:2件、B:1件 → max=2 → A:1.0, B:0.5
    a = out.loc[out["ticker"] == "A", "news_signal"].values[0]
    b = out.loc[out["ticker"] == "B", "news_signal"].values[0]
    assert abs(a - 1.0) < 1e-9
    assert abs(b - 0.5) < 1e-9


