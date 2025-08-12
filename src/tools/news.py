from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Dict


@dataclass
class NewsClient:
    """ニュース取得の薄いIF。MVPはモック/将来はRSS/API連携。
    戻り値: list[dict(ticker,title,url,date)]
    """

    def _fetch(self, tickers: List[str], since: date) -> List[Dict]:
        # MVP: 上位でモンキーパッチ/差し替え前提
        return []

    def get_news(self, tickers: List[str], since: date) -> List[Dict]:
        return self._fetch(tickers, since)


