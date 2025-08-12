from __future__ import annotations

from pathlib import Path
import pandas as pd


def load_universe(region: str) -> pd.DataFrame:
    """`data/universe/{REGION}.csv` を読み、ticker,name を返す。"""
    p = Path(__file__).resolve().parents[2] / "data" / "universe" / f"{region}.csv"
    df = pd.read_csv(p)
    if "ticker" not in df.columns or "name" not in df.columns:
        raise ValueError(f"universe CSV must have ticker,name: {p}")
    return df[["ticker", "name"]].copy()


