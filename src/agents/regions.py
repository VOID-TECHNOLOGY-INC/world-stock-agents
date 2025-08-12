from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from ..scoring.scoring import ScoreWeights, score_candidates
from ..scoring.features import build_features_from_dummy, build_features_from_prices
from ..scoring.normalize import normalize_features
from .openai_agent import is_openai_configured, generate_thesis_and_risks
from ..io.loaders import load_universe
from ..tools.marketdata import MarketDataClient


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
        except Exception:
            df_features = None
        if df_features is None or df_features.empty:
            # フォールバック: ダミー生成
            df_features = build_features_from_dummy(region=self.name, as_of=as_of)
        df_features = normalize_features(df_features)
        df_scored = score_candidates(df_features, ScoreWeights())

        df_top = (
            df_scored.sort_values("score_overall", ascending=False)
            .head(top_n)
            .copy()
        )

        candidates: list[dict[str, Any]] = []
        rng = np.random.default_rng(42)
        for _, row in df_top.iterrows():
            ticker = row["ticker"]
            name = row["name"]
            evidence = [
                {"type": "metric", "name": "ROIC_TTM", "value": round(10 + 20 * rng.random(), 2)},
            ]
            # OpenAIでthesis/risks生成（可能なら）
            features = {
                "fundamental": float(row.get("score_fundamental", 0.0)),
                "technical": float(row.get("score_technical", 0.0)),
                "quality": float(row.get("score_quality", 0.0)),
                "news": float(row.get("score_news", 0.0)),
            }
            if is_openai_configured():
                thesis, risks = generate_thesis_and_risks(ticker, name, self.name, features)
            else:
                thesis, risks = (
                    f"{name} は{self.name}市場の中で相対的に指標が良好。",
                    ["需給変動", "規制", "マクロ要因"],
                )

            candidates.append(
                {
                    "ticker": ticker,
                    "name": name,
                    "score_overall": float(row["score_overall"]),
                    "score_breakdown": {
                        "fundamental": float(row.get("score_fundamental", 0.0)),
                        "technical": float(row.get("score_technical", 0.0)),
                        "quality": float(row.get("score_quality", 0.0)),
                        "news": float(row.get("score_news", 0.0)),
                    },
                    "thesis": thesis,
                    "risks": risks,
                    "evidence": evidence,
                }
            )

        result = {
            "region": self.name,
            "as_of": as_of.strftime("%Y-%m-%d"),
            "universe": self.universe,
            "candidates": candidates,
        }

        return result


