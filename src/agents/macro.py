from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class MacroAgent:
    """マクロ初期重みを提案するエージェント。

    - 既定: 固定の初期重み（US 45%, JP 25%, EU 20%, CN 10%）
    - CSV指定: `csv_path` が与えられた場合、`region,weight` のCSVから読み込み、指定地域のみ正規化して返す
    """

    csv_path: Optional[str] = None
    default_weights: Dict[str, float] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.default_weights is None:
            self.default_weights = {"US": 0.45, "JP": 0.25, "EU": 0.20, "CN": 0.10}

    def _load_csv_weights(self) -> Optional[Dict[str, float]]:
        if not self.csv_path:
            return None
        try:
            import pandas as pd  # lazy import
            df = pd.read_csv(self.csv_path)
            if "region" not in df.columns or "weight" not in df.columns:
                return None
            # マイナスは0にクリップ
            df["weight"] = df["weight"].astype(float).clip(lower=0.0)
            weights: Dict[str, float] = {
                str(r).strip().upper(): float(w)
                for r, w in zip(df["region"], df["weight"]) if pd.notna(r)
            }
            return weights or None
        except Exception:
            return None

    def propose(self, region_list: List[str]) -> Dict[str, float]:
        src = self._load_csv_weights() or self.default_weights
        filt = {r: float(src.get(r, 0.0)) for r in region_list}
        s = sum(filt.values())
        if s <= 0:
            # フォールバック: 均等
            n = max(1, len(region_list))
            return {r: 1.0 / n for r in region_list}
        return {r: v / s for r, v in filt.items()}


