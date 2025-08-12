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


def normalize_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in df.columns:
        if col in ("ticker", "name"):
            continue
        df[col] = _min_max(df[col])
    return df


