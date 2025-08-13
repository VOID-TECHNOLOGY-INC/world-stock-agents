from datetime import date

from src.tools.news import NewsClient


class _DummyTicker:
    def __init__(self, news):
        self.news = news


def test_newsclient_fetch_maps_yfinance_news(monkeypatch):
    # yfinance.Ticker をモック
    def fake_ticker(symbol):
        return _DummyTicker([
            {"title": "A title", "link": "https://ex/a", "providerPublishTime": 1754611200},  # 2025-08-08
            {"title": "B title", "url": "https://ex/b", "providerPublishTime": 1754697600},    # 2025-08-09
        ])

    import builtins
    # モジュールインポート前提: src.tools.news で import yfinance as yf を行うので
    # yfinance.Ticker を差し替える
    import types
    fake_yf = types.SimpleNamespace(Ticker=fake_ticker)

    def fake_import(name, *args, **kwargs):
        if name == "yfinance":
            return fake_yf
        return original_import(name, *args, **kwargs)

    original_import = builtins.__import__
    monkeypatch.setattr(builtins, "__import__", fake_import)

    client = NewsClient()
    out = client.get_news(["AAPL"], date(2025, 8, 8))
    assert isinstance(out, list) and len(out) >= 2
    assert set(out[0].keys()) >= {"ticker", "title", "url", "date"}
    assert all(item["ticker"] == "AAPL" for item in out)


def test_newsclient_fetch_filters_since(monkeypatch):
    def fake_ticker(symbol):
        return _DummyTicker([
            {"title": "Old", "link": "https://ex/old", "providerPublishTime": 1704067200},  # 2024-01-01
            {"title": "New", "link": "https://ex/new", "providerPublishTime": 1754784000},  # 2025-08-10
        ])

    import builtins, types
    fake_yf = types.SimpleNamespace(Ticker=fake_ticker)

    def fake_import(name, *args, **kwargs):
        if name == "yfinance":
            return fake_yf
        return original_import(name, *args, **kwargs)

    original_import = builtins.__import__
    monkeypatch.setattr(builtins, "__import__", fake_import)

    client = NewsClient()
    out = client.get_news(["MSFT"], date(2025, 8, 9))
    # since 以降のみ残る
    assert len(out) == 1
    assert out[0]["title"] == "New"


