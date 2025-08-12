from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from scipy.optimize import minimize


@dataclass
class MVConfig:
    target: str = "min_vol"  # or "max_return"
    region_limits: Dict[str, float] | None = None
    position_limit: float = 0.07
    cash_bounds: Tuple[float, float] = (0.0, 0.1)


def _apply_region_constraints(tickers: List[str], regions: List[str], region_limits: Dict[str, float]) -> List[Tuple[int, float]]:
    """各地域の合計重みに上限。返り値は (index, coeff) 形式の線形制約係数生成は簡略化し、
    scipyのlinear constraintsは個別に定義する。
    ここではハンドリングを呼び出し側に委ねるため、ダミーを返す（実際の制約は目的関数内でペナルティ）。"""
    return []


def optimize_mean_variance(
    tickers: List[str],
    regions: List[str],
    mu: pd.Series | None,
    cov: pd.DataFrame,
    cfg: MVConfig,
) -> np.ndarray:
    n = len(tickers)
    x0 = np.array([min(cfg.position_limit, 1.0 / max(1, n))] * n)
    bounds = [(0.0, cfg.position_limit)] * n

    # 目的関数
    def obj(w: np.ndarray) -> float:
        var = float(np.dot(w, cov.values @ w))
        if cfg.target == "max_return" and mu is not None:
            ret = float(np.dot(w, mu.loc[tickers].fillna(0.0).values))
            return var - 1.0 * ret  # 簡易: リスクとリターンのトレードオフ
        return var

    # 総和 + 現金の範囲は後で正規化するため、ここでは Σw <= 1 を制約
    constraints = [
        {"type": "ineq", "fun": lambda w: 1.0 - np.sum(w)},
    ]

    # 地域ペナルティ（上限超過に罰則）
    region_limits = cfg.region_limits or {}
    unique_regions = sorted(set(regions))
    region_to_idx = {r: [i for i, rr in enumerate(regions) if rr == r] for r in unique_regions}

    def penalized_obj(w: np.ndarray) -> float:
        base = obj(w)
        pen = 0.0
        for r, idx in region_to_idx.items():
            cap = float(region_limits.get(r, 1.0))
            s = float(np.sum(w[idx]))
            if s > cap:
                pen += 1e3 * (s - cap) ** 2
        return base + pen

    res = minimize(
        penalized_obj, x0, method="SLSQP", bounds=bounds, constraints=constraints, options={"maxiter": 500}
    )
    w = res.x if res.success else x0
    # 現金に収める
    total = float(np.sum(w))
    if total > 1.0:
        w = w / total
    return w


