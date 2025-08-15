from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, Optional
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import BoundedSemaphore
import time
import logging

import pandas as pd


@dataclass
class MarketDataClient:
    """市場データ取得（yfinanceバックエンド）。

    get_prices: 指定ティッカーの終値と出来高を返す。
    戻り値: (prices_df, volumes_df)
      - rows: DatetimeIndex（日次）
      - cols: ティッカー
    """
    
    def __init__(self, max_workers: int = 1, retry_attempts: int = 3, retry_delay: float = 1.0, global_limit: int = 6, request_interval: float = 0.5):
        self.max_workers = max_workers  # レート制限対策でデフォルト1に変更
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.request_interval = request_interval  # リクエスト間隔（秒）
        self._cache = {}  # 簡易キャッシュ（同日内の同一ティッカー取得を再利用）
        # ランタイム全体の同時ダウンロード制限（プロセス内共有）
        # NOTE: インスタンス間で共有したいが、簡便にインスタンスごとに上限を設ける
        self._gate = BoundedSemaphore(value=max(1, global_limit))

    def _download_single_ticker_with_retry(self, ticker: str, period: str, lookback_days: int) -> Optional[Tuple[pd.Series, pd.Series]]:
        """単一ティッカーのダウンロード（リトライ付き）"""
        import yfinance as yf
        
        for attempt in range(self.retry_attempts):
            try:
                # tickersパラメータを文字列として渡す
                # 一部環境で ignore_tz が未対応なためフォールバック
                with self._gate:
                    try:
                        d = yf.download(
                            tickers=str(ticker), 
                            period=period, 
                            interval="1d", 
                            auto_adjust=True, 
                            progress=False,
                            threads=False,
                            ignore_tz=True
                        )
                    except TypeError:
                        d = yf.download(
                            tickers=str(ticker), 
                            period=period, 
                            interval="1d", 
                            auto_adjust=True, 
                            progress=False,
                            threads=False
                        )
                if d is not None and not d.empty:
                    cp = d["Close"].rename(ticker)
                    cv = d["Volume"].rename(ticker)
                    cutoff = (datetime.utcnow() - timedelta(days=lookback_days)).date()
                    cp = cp.loc[cp.index.date >= cutoff]
                    cv = cv.loc[cv.index.date >= cutoff]
                    
                    # 成功時はリクエスト間隔を設ける（レート制限対策）
                    time.sleep(self.request_interval)
                    return cp, cv
                # 空返却は失敗扱いとしてリトライ
                continue
            except Exception as e:
                if attempt < self.retry_attempts - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))  # 指数バックオフ
                    continue
                logging.warning(f"Failed to download {ticker} after {self.retry_attempts} attempts: {type(e).__name__}: {e}")
                return None
        return None

    def _download_batch_tickers(self, tickers: List[str], period: str, lookback_days: int) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """バッチでティッカーを並列ダウンロード"""
        if not tickers:
            return pd.DataFrame(), pd.DataFrame()
        
        frames_p = []
        frames_v = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 並列でダウンロード
            future_to_ticker = {
                executor.submit(self._download_single_ticker_with_retry, t, period, lookback_days): t 
                for t in tickers
            }
            
            for future in as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                try:
                    result = future.result()
                    if result is not None:
                        cp, cv = result
                        frames_p.append(cp.to_frame())
                        frames_v.append(cv.to_frame())
                except Exception as e:
                    logging.warning(f"Error downloading {ticker}: {type(e).__name__}: {e}")
                    continue
        
        prices = pd.concat(frames_p, axis=1) if frames_p else pd.DataFrame()
        volumes = pd.concat(frames_v, axis=1) if frames_v else pd.DataFrame()
        
        return prices, volumes

    def get_prices(self, tickers: List[str], lookback_days: int = 260) -> Tuple[pd.DataFrame, pd.DataFrame]:
        import yfinance as yf  # optional import

        if not tickers:
            return pd.DataFrame(), pd.DataFrame()
        
        # キャッシュチェック
        cache_key = f"{','.join(sorted(tickers))}_{lookback_days}"
        today = datetime.now().date()
        if cache_key in self._cache and self._cache[cache_key]['date'] == today:
            return self._cache[cache_key]['prices'], self._cache[cache_key]['volumes']
        
        # yfinanceは期間指定の方が速い
        period = "2y" if lookback_days > 252 else "1y"
        
        # まずバッチダウンロードを試行（リトライ付き）
        # 内部スレッドはOFFにし、外側の制御に委ねる
        data = None
        for attempt in range(self.retry_attempts):
            try:
                try:
                    data = yf.download(
                        tickers=tickers,
                        period=period,
                        interval="1d",
                        group_by="ticker",
                        auto_adjust=True,
                        threads=False,
                        progress=False,
                        ignore_tz=True
                    )
                except TypeError:
                    data = yf.download(
                        tickers=tickers,
                        period=period,
                        interval="1d",
                        group_by="ticker",
                        auto_adjust=True,
                        threads=False,
                        progress=False
                    )
                break
            except Exception as e:
                if attempt < self.retry_attempts - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))  # 指数バックオフ
                    continue
                logging.warning(
                    f"Batch download failed for {len(tickers)} tickers after {self.retry_attempts} attempts: {type(e).__name__}: {e}"
                )
                data = pd.DataFrame()

        # single vs multi ticker で形が変わる
        def extract(field: str) -> pd.DataFrame:
            if isinstance(data.columns, pd.MultiIndex):
                # カラム: (ticker, field)
                frames = []
                for t in tickers:
                    if (t, field) in data.columns:
                        s = data[(t, field)].rename(t)
                        frames.append(s)
                return pd.concat(frames, axis=1) if frames else pd.DataFrame()
            else:
                # 単一ティッカー
                if field in data.columns:
                    return pd.DataFrame({tickers[0]: data[field]})
                return pd.DataFrame()

        prices = extract("Close") if data is not None else pd.DataFrame()
        volumes = extract("Volume") if data is not None else pd.DataFrame()

        # フィルタ: 直近 lookback_days に限定（.last の代替）
        if prices is not None and not prices.empty:
            cutoff = (datetime.utcnow() - timedelta(days=lookback_days)).date()
            prices = prices.loc[prices.index.date >= cutoff]
        if volumes is not None and not volumes.empty:
            cutoff = (datetime.utcnow() - timedelta(days=lookback_days)).date()
            volumes = volumes.loc[volumes.index.date >= cutoff]

        # 欠落ティッカーの並列補完
        missing = [t for t in tickers if prices is None or t not in prices.columns]
        if missing:
            # バッチサイズを制御（レート制限対策）
            batch_size = min(10, len(missing))  # バッチサイズを小さく
            missing_batches = [missing[i:i + batch_size] for i in range(0, len(missing), batch_size)]
            
            frames_p = [] if prices is None or prices.empty else [prices]
            frames_v = [] if volumes is None or volumes.empty else [volumes]
            
            for batch_idx, batch in enumerate(missing_batches):
                if batch_idx > 0:
                    # バッチ間隔を設ける（レート制限対策）
                    time.sleep(2.0)
                    logging.info(f"Processing missing tickers batch {batch_idx + 1}/{len(missing_batches)}")
                
                batch_prices, batch_volumes = self._download_batch_tickers(batch, period, lookback_days)
                if not batch_prices.empty:
                    frames_p.append(batch_prices)
                if not batch_volumes.empty:
                    frames_v.append(batch_volumes)
            
            if frames_p:
                prices = pd.concat(frames_p, axis=1)
            if frames_v:
                volumes = pd.concat(frames_v, axis=1)

        # キャッシュに保存
        self._cache[cache_key] = {
            'date': today,
            'prices': prices if prices is not None else pd.DataFrame(),
            'volumes': volumes if volumes is not None else pd.DataFrame()
        }

        return prices if prices is not None else pd.DataFrame(), volumes if volumes is not None else pd.DataFrame()


