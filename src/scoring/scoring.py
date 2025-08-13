from __future__ import annotations

from dataclasses import dataclass
import pandas as pd


@dataclass
class ScoreWeights:
    fundamental: float = 0.4
    technical: float = 0.35
    quality: float = 0.15
    news: float = 0.10
    growth: float = 0.0  # 既存スコアに影響しない初期値（必要に応じて引き上げ）


def score_candidates(df_features: pd.DataFrame, weights: ScoreWeights) -> pd.DataFrame:
    """特徴量を合成してスコアリング。

    入力: normalize済みの特徴量
    出力: score_fundamental, score_technical, score_quality, score_news, score_overall
    """
    df = df_features.copy()
    df["score_fundamental"] = (
        df[["fundamental_roic", "fundamental_fcf_margin"]].mean(axis=1)
    )
    df["score_technical"] = (
        df[["technical_mom_12m", "technical_volume_trend"]].mean(axis=1)
    )
    df["score_quality"] = df[["quality_dilution"]].mean(axis=1)
    df["score_news"] = df[["news_signal"]].mean(axis=1)
    # 成長（列がなければ0.5で安全に平均化）
    if "growth_revenue_cagr" not in df.columns:
        df["growth_revenue_cagr"] = 0.5
    if "growth_eps_growth" not in df.columns:
        df["growth_eps_growth"] = 0.5
    df["score_growth"] = df[["growth_revenue_cagr", "growth_eps_growth"]].mean(axis=1)

    df["score_overall"] = (
        weights.fundamental * df["score_fundamental"]
        + weights.technical * df["score_technical"]
        + weights.quality * df["score_quality"]
        + weights.news * df["score_news"]
        + weights.growth * df["score_growth"]
    )
    return df


