from __future__ import annotations

from dataclasses import dataclass
from typing import List

import pandas as pd


@dataclass
class FundamentalsClient:
    """Fundamentals via yfinance/yahooquery (MVP: 実装容易性重視の薄いラッパ)。
    本番では安定APIに差し替え可能なIFを維持する。
    """

    def _fetch(self, tickers: List[str], fields: List[str]) -> pd.DataFrame:
        # MVP: yfinance の info/sustainability 等はレート・安定性の問題があるため、
        # 将来 yahooquery などに差し替える前提の仮実装とする。
        import yfinance as yf
        rows = []
        for t in tickers:
            try:
                tk = yf.Ticker(t)
                info = tk.get_info() if hasattr(tk, "get_info") else getattr(tk, "info", {})
            except Exception:
                info = {}
            row = {"ticker": t}
            for f in fields:
                row[f] = info.get(f) if isinstance(info, dict) else None
            rows.append(row)
        return pd.DataFrame(rows)

    def get_fundamentals(self, tickers: List[str], fields: List[str]) -> pd.DataFrame:
        df = self._fetch(tickers, fields)
        if "ticker" not in df.columns:
            df.insert(0, "ticker", tickers)
        return df


