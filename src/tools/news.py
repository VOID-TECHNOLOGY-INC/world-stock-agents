from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import logging


@dataclass
class NewsClient:
    """ニュース取得の薄いIF。MVPはモック/将来はRSS/API連携。
    戻り値: list[dict(ticker,title,url,date)]
    """
    
    def __init__(self, max_workers: int = 3, retry_attempts: int = 2, retry_delay: float = 0.5):
        self.max_workers = max_workers  # レート制限を考慮して控えめに
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self._cache = {}  # 簡易キャッシュ

    def _fetch_single_ticker_with_retry(self, ticker: str, since: date) -> List[Dict]:
        """単一ティッカーのニュース取得（リトライ付き）"""
        items: List[Dict] = []
        
        try:
            import yfinance as yf  # optional dependency at runtime
        except Exception:
            return items

        for attempt in range(self.retry_attempts):
            try:
                tk = yf.Ticker(ticker)
                news_list = getattr(tk, "news", None)
                if not news_list:
                    break
                
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
                            "ticker": ticker,
                            "title": title,
                            "url": url,
                            "date": dt_str,
                        })
                
                # 成功したらループを抜ける
                break
                
            except Exception as e:
                if attempt < self.retry_attempts - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))  # 指数バックオフ
                    continue
                logging.warning(f"Failed to fetch news for {ticker} after {self.retry_attempts} attempts: {e}")
                break

        return items

    def _fetch(self, tickers: List[str], since: date) -> List[Dict]:
        # キャッシュチェック
        cache_key = f"{','.join(sorted(tickers))}_{since.isoformat()}"
        today = date.today()
        if cache_key in self._cache and self._cache[cache_key]['date'] == today:
            return self._cache[cache_key]['items']
        
        items: List[Dict] = []
        
        if not tickers:
            return items
        
        # 並列でニュース取得
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_ticker = {
                executor.submit(self._fetch_single_ticker_with_retry, t, since): t 
                for t in tickers
            }
            
            for future in as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                try:
                    ticker_items = future.result()
                    items.extend(ticker_items)
                except Exception as e:
                    logging.warning(f"Error fetching news for {ticker}: {e}")
                    continue
        
        # キャッシュに保存
        self._cache[cache_key] = {
            'date': today,
            'items': items
        }
        
        return items

    def get_news(self, tickers: List[str], since: date) -> List[Dict]:
        return self._fetch(tickers, since)


