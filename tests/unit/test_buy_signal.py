from src.tools.buy_signal import evaluate_buy_signals


def test_evaluate_buy_signals_decision():
    """Stocks meeting enough criteria are marked as BUY."""

    def fake_fetcher(ticker: str):
        data = {
            "AAA": {
                "pe": 10.0,
                "pb": 1.0,
                "revenue_growth": 0.10,
                "eps_growth": 0.20,
                "peg_ratio": 0.8,
            },
            "BBB": {
                "pe": 20.0,
                "pb": 2.0,
                "revenue_growth": 0.02,
                "eps_growth": -0.05,
                "peg_ratio": 2.0,
            },
        }
        return data[ticker]

    df = evaluate_buy_signals(["AAA", "BBB"], fetcher=fake_fetcher)

    expected_cols = {
        "ticker",
        "pe",
        "pb",
        "revenue_growth",
        "eps_growth",
        "peg_ratio",
        "score",
        "decision",
    }
    assert set(df.columns) == expected_cols

    row_a = df[df["ticker"] == "AAA"].iloc[0]
    row_b = df[df["ticker"] == "BBB"].iloc[0]
    assert row_a["decision"] == "BUY"
    assert row_b["decision"] == "HOLD"
