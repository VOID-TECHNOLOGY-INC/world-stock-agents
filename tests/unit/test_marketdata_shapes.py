import types
import pandas as pd

from src.tools.marketdata import MarketDataClient


class _DLResult:
    # Mimic yfinance.download returning MultiIndex columns
    def __init__(self):
        idx = pd.date_range("2025-01-01", periods=3, freq="D")
        self._df = pd.DataFrame({
            ("A", "Close"): [10, 10.5, 10.7],
            ("A", "Volume"): [100, 110, 120],
            ("B", "Close"): [20, 20.1, 20.2],
            ("B", "Volume"): [200, 210, 220],
        }, index=idx)
        self._df.columns = pd.MultiIndex.from_tuples(self._df.columns)

    @property
    def columns(self):
        return self._df.columns

    def __getitem__(self, key):
        return self._df[key]


def test_marketdata_handles_multiindex(monkeypatch):
    def fake_download(*args, **kwargs):
        return _DLResult()

    import builtins
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "yfinance":
            return types.SimpleNamespace(download=fake_download)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    cli = MarketDataClient()
    prices, volumes = cli.get_prices(["A", "B"], lookback_days=10)
    assert set(prices.columns) == {"A", "B"}
    assert set(volumes.columns) == {"A", "B"}


