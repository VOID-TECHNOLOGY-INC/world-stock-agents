import pandas as pd
from datetime import date

from src.scoring.features import merge_news_signal


def test_merge_news_signal_uses_sentiment_when_available():
    features_df = pd.DataFrame({
        "ticker": ["A"],
        "name": ["A"],
        "news_signal": [0.5],
    })
    news_items = [
        {"ticker": "A", "title": "Earnings beat and raises guidance", "url": "u", "date": str(date(2025, 8, 1))},
        {"ticker": "A", "title": "Upgrade to outperform", "url": "u2", "date": str(date(2025, 8, 2))},
    ]
    out = merge_news_signal(features_df, news_items)
    # 正のセンチメントなので 0.5 より上にシフトするはず
    assert out.loc[0, "news_signal"] > 0.5


def test_merge_news_signal_falls_back_to_counts_when_no_titles():
    features_df = pd.DataFrame({
        "ticker": ["A", "B"],
        "name": ["A", "B"],
        "news_signal": [0.1, 0.9],
    })
    news_items = [
        {"ticker": "A", "url": "u", "date": str(date(2025, 8, 1))},
        {"ticker": "A", "url": "u2", "date": str(date(2025, 8, 2))},
        {"ticker": "B", "url": "u3", "date": str(date(2025, 8, 3))},
    ]
    out = merge_news_signal(features_df, news_items)
    a = out.loc[out["ticker"] == "A", "news_signal"].values[0]
    b = out.loc[out["ticker"] == "B", "news_signal"].values[0]
    assert a > b


