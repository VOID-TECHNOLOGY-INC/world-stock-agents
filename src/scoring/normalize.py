from __future__ import annotations

import pandas as pd


def _min_max(col: pd.Series) -> pd.Series:
    # NaNを一旦補完
    if col.isna().all():
        return pd.Series([0.5] * len(col), index=col.index)
    filled = col.fillna(col.median())
    lo, hi = filled.min(), filled.max()
    if hi == lo:
        return pd.Series([0.5] * len(col), index=col.index)
    scaled = (filled - lo) / (hi - lo)
    return scaled.clip(0.0, 1.0)


def normalize_growth_rate(rate: float) -> float:
    """成長率を0-1の範囲に正規化（極端な値を制限）
    
    Args:
        rate: 成長率（例: 0.25 = 25%成長）
    
    Returns:
        正規化された値（0-1）
    """
    if pd.isna(rate):
        return 0.5
    
    # 極端な成長率の処理
    if rate > 2.0:  # 200%以上の成長率
        return 1.0
    elif rate < -0.5:  # -50%以下の成長率
        return 0.0
    else:
        # -50% to +200% → 0 to 1
        return (rate + 0.5) / 2.5


def normalize_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in df.columns:
        if col in ("ticker", "name"):
            continue
        df[col] = _min_max(df[col])
    return df


