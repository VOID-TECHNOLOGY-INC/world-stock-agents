import pandas as pd

from src.scoring.scoring import ScoreWeights, score_candidates


def test_score_candidates_handles_missing_growth_columns():
    df = pd.DataFrame({
        "ticker": ["A", "B"],
        "name": ["A", "B"],
        "fundamental_roic": [0.2, 0.8],
        "fundamental_fcf_margin": [0.3, 0.7],
        "technical_mom_12m": [0.5, 0.6],
        "technical_volume_trend": [0.4, 0.5],
        "quality_dilution": [0.6, 0.4],
        "news_signal": [0.5, 0.5],
    })
    out = score_candidates(df, ScoreWeights())
    assert "score_overall" in out.columns
    assert "score_growth" in out.columns
    assert out.shape[0] == 2


