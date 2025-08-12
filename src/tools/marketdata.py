from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple
from datetime import datetime, timedelta

import pandas as pd


@dataclass
class MarketDataClient:
    """市場データ取得（yfinanceバックエンド）。

    get_prices: 指定ティッカーの終値と出来高を返す。
    戻り値: (prices_df, volumes_df)
      - rows: DatetimeIndex（日次）
      - cols: ティッカー
    """

    def get_prices(self, tickers: List[str], lookback_days: int = 260) -> Tuple[pd.DataFrame, pd.DataFrame]:
        import yfinance as yf  # optional import

        if not tickers:
            return pd.DataFrame(), pd.DataFrame()
        # yfinanceは期間指定の方が速い
        period = "2y" if lookback_days > 252 else "1y"
        data = yf.download(
            tickers=tickers,
            period=period,
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            threads=True,
            progress=False,
        )

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

        prices = extract("Close")
        volumes = extract("Volume")

        # フィルタ: 直近 lookback_days に限定（.last の代替）
        if prices is not None and not prices.empty:
            cutoff = (datetime.utcnow() - timedelta(days=lookback_days)).date()
            prices = prices.loc[prices.index.date >= cutoff]
        if volumes is not None and not volumes.empty:
            cutoff = (datetime.utcnow() - timedelta(days=lookback_days)).date()
            volumes = volumes.loc[volumes.index.date >= cutoff]

        # もしすべて空 or 必要ティッカーが欠ける場合は個別取得で補完
        missing = [t for t in tickers if prices is None or t not in prices.columns]
        if missing:
            frames_p = [] if prices is None or prices.empty else [prices]
            frames_v = [] if volumes is None or volumes.empty else [volumes]
            for t in missing:
                try:
                    d = yf.download(tickers=t, period=period, interval="1d", auto_adjust=True, progress=False)
                    if not d.empty:
                        cp = d["Close"].rename(t)
                        cv = d["Volume"].rename(t)
                        cutoff = (datetime.utcnow() - timedelta(days=lookback_days)).date()
                        cp = cp.loc[cp.index.date >= cutoff]
                        cv = cv.loc[cv.index.date >= cutoff]
                        frames_p.append(cp.to_frame())
                        frames_v.append(cv.to_frame())
                except Exception:
                    continue
            prices = pd.concat(frames_p, axis=1) if frames_p else pd.DataFrame()
            volumes = pd.concat(frames_v, axis=1) if frames_v else pd.DataFrame()

        return prices if prices is not None else pd.DataFrame(), volumes if volumes is not None else pd.DataFrame()


