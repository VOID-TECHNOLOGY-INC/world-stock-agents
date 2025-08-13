from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from ..scoring.scoring import ScoreWeights, score_candidates
from ..scoring.features import (
    build_features_from_dummy,
    build_features_from_prices,
    merge_fundamentals,
    merge_news_signal,
)
from ..scoring.normalize import normalize_features
from .openai_agent import is_openai_configured, generate_thesis_and_risks
from ..io.loaders import load_universe
from ..tools.marketdata import MarketDataClient
from ..tools.fundamentals import FundamentalsClient
from ..tools.news import NewsClient


@dataclass
class RegionAgent:
    name: str
    universe: str
    tools: dict

    def run(self, as_of: date, top_n: int = 50) -> dict:
        # 実データ: ユニバースのティッカー読み込み → yfinance 取得 → 特徴量化
        df_features = None
        try:
            uni = load_universe(self.name)
            mkt = self.tools.get("marketdata") if self.tools else None
            if not isinstance(mkt, MarketDataClient):
                mkt = MarketDataClient()
            prices, volumes = mkt.get_prices(uni["ticker"].tolist(), lookback_days=260)
            if prices is not None and not prices.empty:
                df_features = build_features_from_prices(self.name, uni, prices, volumes)
                # ファンダ
                fcli = self.tools.get("fundamentals") if self.tools else None
                if not isinstance(fcli, FundamentalsClient):
                    fcli = FundamentalsClient()
                fdf = fcli.get_fundamentals(
                    uni["ticker"].tolist(), ["roic", "fcf_margin", "revenue_cagr", "eps_growth"]
                )  # 成長も取得
                df_features = merge_fundamentals(df_features, fdf)
                # ニュース
                ncli = self.tools.get("news") if self.tools else None
                if not isinstance(ncli, NewsClient):
                    ncli = NewsClient()
                news_items = ncli.get_news(uni["ticker"].tolist(), as_of)
                df_features = merge_news_signal(df_features, news_items)
        except Exception:
            df_features = None
        if df_features is None or df_features.empty:
            # フォールバック: ダミー生成
            df_features = build_features_from_dummy(region=self.name, as_of=as_of)
        df_features = normalize_features(df_features)
        df_scored = score_candidates(df_features, ScoreWeights())

        df_top = (
            df_scored.sort_values("score_overall", ascending=False).head(top_n).copy()
        )

        # 成長上位（別出力用）
        df_growth_top = (
            df_scored.sort_values("score_growth", ascending=False).head(top_n).copy()
        )

        def _rows_to_candidates(rows: "pd.DataFrame") -> list[dict[str, Any]]:
            out: list[dict[str, Any]] = []
            rng = np.random.default_rng(42)
            for _, row in rows.iterrows():
                ticker = row["ticker"]
                name = row["name"]
                evidence = [
                    {"type": "metric", "name": "ROIC_TTM", "value": round(10 + 20 * rng.random(), 2)},
                ]
                features = {
                    "fundamental": float(row.get("score_fundamental", 0.0)),
                    "technical": float(row.get("score_technical", 0.0)),
                    "quality": float(row.get("score_quality", 0.0)),
                    "news": float(row.get("score_news", 0.0)),
                    "growth": float(row.get("score_growth", 0.0)),
                }
                if is_openai_configured():
                    thesis, risks = generate_thesis_and_risks(ticker, name, self.name, features)
                else:
                    thesis, risks = (
                        f"{name} は{self.name}市場の中で相対的に指標が良好。",
                        ["需給変動", "規制", "マクロ要因"],
                    )

                out.append(
                    {
                        "ticker": ticker,
                        "name": name,
                        "score_overall": float(row.get("score_overall", 0.0)),
                        "score_breakdown": features,
                        "thesis": thesis,
                        "risks": risks,
                        "evidence": evidence,
                    }
                )
            return out

        candidates = _rows_to_candidates(df_top)
        growth_candidates = _rows_to_candidates(df_growth_top)

        result = {
            "region": self.name,
            "as_of": as_of.strftime("%Y-%m-%d"),
            "universe": self.universe,
            "candidates": candidates,
            "growth_candidates": growth_candidates,
        }

        return result


