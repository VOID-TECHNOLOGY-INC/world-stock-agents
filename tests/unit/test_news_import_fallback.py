from datetime import date

from src.tools.news import NewsClient


def test_news_import_failure_returns_empty(monkeypatch):
    # yfinance import を失敗させる
    import builtins
    orig_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "yfinance":
            raise ImportError("yfinance not available")
        return orig_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    client = NewsClient()
    out = client.get_news(["AAPL"], date(2025, 8, 12))
    assert out == []


