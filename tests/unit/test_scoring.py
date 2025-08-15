import numpy as np
import pandas as pd
import pytest

from src.scoring.normalize import normalize_features, normalize_growth_rate
from src.scoring.scoring import ScoreWeights, score_candidates


def test_normalize_features_handles_constant_and_nan():
    df = pd.DataFrame({
        "ticker": ["A", "B", "C"],
        "name": ["A", "B", "C"],
        "value": [1.0, 1.0, 1.0],  # 定数
        "nan_value": [1.0, float("nan"), 2.0],  # NaN含む
    })
    result = normalize_features(df)
    assert result["value"].iloc[0] == 0.5  # 定数は0.5
    assert result["nan_value"].iloc[1] == 0.5  # NaNは中央値で補完


def test_score_candidates_basic():
    df = pd.DataFrame({
        "ticker": ["A", "B"],
        "fundamental_roic": [0.8, 0.2],
        "fundamental_fcf_margin": [0.9, 0.1],
        "technical_mom_12m": [0.7, 0.3],
        "technical_volume_trend": [0.6, 0.4],
        "quality_dilution": [0.5, 0.5],
        "news_signal": [0.4, 0.6],
        "growth_revenue_cagr": [0.3, 0.7],
        "growth_eps_growth": [0.2, 0.8],
    })
    weights = ScoreWeights()
    result = score_candidates(df, weights)
    
    # 成長スコアが有効になっていることを確認
    assert "score_growth" in result.columns
    assert result["score_growth"].iloc[0] == 0.25  # (0.3 + 0.2) / 2
    assert result["score_growth"].iloc[1] == 0.75  # (0.7 + 0.8) / 2
    
    # 総合スコアに成長スコアが反映されていることを確認
    assert "score_overall" in result.columns


def test_normalize_growth_rate():
    # 正常な成長率
    assert abs(normalize_growth_rate(0.0) - 0.2) < 1e-9  # 0% → 0.2
    assert abs(normalize_growth_rate(0.25) - 0.3) < 1e-9  # 25% → 0.3
    assert abs(normalize_growth_rate(0.5) - 0.4) < 1e-9   # 50% → 0.4
    
    # 極端な成長率の制限
    assert normalize_growth_rate(3.0) == 1.0  # 300% → 1.0
    assert normalize_growth_rate(-0.6) == 0.0  # -60% → 0.0
    
    # NaN処理
    assert normalize_growth_rate(float("nan")) == 0.5

