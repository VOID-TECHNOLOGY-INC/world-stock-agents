from src.tools.fundamentals import FundamentalsClient


def test_fundamentals_returns_dataframe_with_requested_fields(monkeypatch):
    client = FundamentalsClient()

    def mock_fetch_raw(tickers):
        return {t: {} for t in tickers}

    def mock_compute(raw, fields):
        import pandas as pd
        tickers = list(raw.keys())
        return pd.DataFrame({
            "ticker": tickers,
            fields[0]: [1.0] * len(tickers),
            fields[1]: [2.0] * len(tickers),
        })

    monkeypatch.setattr(client, "_fetch_raw_financials", mock_fetch_raw)
    monkeypatch.setattr(client, "_compute_fields", mock_compute)
    df = client.get_fundamentals(["AAPL", "MSFT"], ["roic", "fcf_margin"])
    assert set(df.columns) >= {"ticker", "roic", "fcf_margin"}
    assert df.shape[0] == 2


def test_fundamentals_computed_metrics(monkeypatch):
    client = FundamentalsClient()

    # モック: 最低限の財務データ
    def mock_fetch_raw(tickers):
        import pandas as pd
        return {
            "AAPL": {
                "revenue_ttm": 400.0,
                "revenue_prev_ttm": 360.0,
                "eps_ttm": 6.0,
                "eps_prev_ttm": 5.0,
                "ebitda_ttm": 120.0,
                "net_debt": 20.0,
                "nopat_ttm": 80.0,
                "invested_capital": 400.0,
                "fcf_ttm": 60.0,
            },
        }

    monkeypatch.setattr(client, "_fetch_raw_financials", mock_fetch_raw)
    out = client.get_fundamentals(["AAPL"], [
        "roic", "fcf_margin", "revenue_cagr", "eps_growth", "net_debt_to_ebitda"
    ])
    row = out.iloc[0].to_dict()
    # ROIC = 80/400 = 0.2
    assert abs(row["roic"] - 0.2) < 1e-6
    # FCF margin = 60/400 = 0.15
    assert abs(row["fcf_margin"] - 0.15) < 1e-6
    # Revenue CAGR (TTM対TTMの単期成長率として近似) = 400/360 - 1 ≈ 0.1111
    assert abs(row["revenue_cagr"] - (400.0/360.0 - 1.0)) < 1e-6
    # EPS growth = 6/5 - 1 = 0.2
    assert abs(row["eps_growth"] - 0.2) < 1e-6
    # NetDebt/EBITDA = 20/120 ≈ 0.1667
    assert abs(row["net_debt_to_ebitda"] - (20.0/120.0)) < 1e-6

