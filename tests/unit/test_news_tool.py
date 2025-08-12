from datetime import date, timedelta
from src.tools.news import NewsClient


def test_news_returns_list_of_items(monkeypatch):
    client = NewsClient()

    def mock_fetch(tickers, since):
        return [
            {"ticker": tickers[0], "title": "Earnings beat", "url": "https://example.com/a", "date": str(since)},
            {"ticker": tickers[0], "title": "Guide raised", "url": "https://example.com/b", "date": str(since + timedelta(days=1))},
        ]

    monkeypatch.setattr(client, "_fetch", mock_fetch)
    out = client.get_news(["AAPL"], date(2025, 8, 1))
    assert isinstance(out, list) and len(out) >= 1
    assert set(out[0].keys()) >= {"ticker", "title", "url", "date"}

