from src.tools.fundamentals import FundamentalsClient


def test_fundamentals_returns_dataframe_with_requested_fields(monkeypatch):
    client = FundamentalsClient()

    def mock_fetch(tickers, fields):
        import pandas as pd
        return pd.DataFrame({
            "ticker": tickers,
            fields[0]: [1.0] * len(tickers),
            fields[1]: [2.0] * len(tickers),
        })

    monkeypatch.setattr(client, "_fetch", mock_fetch)
    df = client.get_fundamentals(["AAPL", "MSFT"], ["roic", "fcf_margin"])
    assert set(df.columns) >= {"ticker", "roic", "fcf_margin"}
    assert df.shape[0] == 2

