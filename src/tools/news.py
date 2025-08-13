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
        # MVP実装: yfinance.Ticker.news を使用し、ティッカーごとのニュースを取得。
        # - ネットワーク失敗や未対応環境でも安全に動作するようにtry/exceptで保護
        # - since 以降の日付のニュースのみ返却
        # - 戻り値は {ticker,title,url,date}（dateはYYYY-MM-DDのISO文字列）
        items: List[Dict] = []
        try:
            import yfinance as yf  # optional dependency at runtime
        except Exception:
            return items

        for t in tickers or []:
            try:
                tk = yf.Ticker(t)
                news_list = getattr(tk, "news", None)
                if not news_list:
                    continue
                for n in news_list:
                    title = n.get("title") or n.get("headline")
                    url = n.get("link") or n.get("url")
                    # yfinanceは providerPublishTime (epoch秒) を持つことが多い
                    pub_ts = n.get("providerPublishTime") or n.get("published_at") or n.get("pubDate")
                    dt_str = None
                    if isinstance(pub_ts, (int, float)):
                        from datetime import datetime, timezone
                        dt = datetime.fromtimestamp(float(pub_ts), tz=timezone.utc).date()
                        dt_str = dt.isoformat()
                    elif isinstance(pub_ts, str):
                        # 文字列はそのまま日付部分を使用（失敗時はスキップ）
                        try:
                            from datetime import datetime
                            dt = datetime.fromisoformat(pub_ts.replace("Z", "+00:00")).date()
                            dt_str = dt.isoformat()
                        except Exception:
                            # RSSのようなフォーマットは一旦無視
                            dt_str = None
                    # フォールバック: 取得日を使用
                    if not dt_str:
                        dt_str = date.today().isoformat()

                    # since 以降のみ
                    try:
                        if dt_str < since.isoformat():
                            continue
                    except Exception:
                        pass

                    if title and url:
                        items.append({
                            "ticker": t,
                            "title": title,
                            "url": url,
                            "date": dt_str,
                        })
            except Exception:
                # 個別ティッカー失敗は無視
                continue

        return items

    def get_news(self, tickers: List[str], since: date) -> List[Dict]:
        return self._fetch(tickers, since)


