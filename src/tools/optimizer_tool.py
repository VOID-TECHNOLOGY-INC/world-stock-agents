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
    risk_aversion: float = 0.0  # 0→ボラ最小、値を上げるとリターン重視
    target_vol: float | None = None  # 年率ボラ上限（例: 0.18）。未指定なら制約なし

    def __post_init__(self) -> None:
        if self.risk_aversion < 0:
            raise ValueError("risk_aversion must be non-negative")
        if self.target_vol is not None and self.target_vol <= 0:
            raise ValueError("target_vol must be positive")
        if self.target not in ("min_vol", "max_return"):
            raise ValueError("target must be 'min_vol' or 'max_return'")


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
        ret = 0.0
        if mu is not None:
            ret = float(np.dot(w, mu.loc[tickers].fillna(0.0).values))
        # リスク許容度が指定されていればトレードオフ優先
        if cfg.risk_aversion > 0 and mu is not None:
            return var - float(cfg.risk_aversion) * ret
        # それ以外でmax_returnが指定されていれば純粋な最大化
        if cfg.target == "max_return" and mu is not None:
            return -ret
        # デフォルトは最小分散
        return var

    # 投資比率の下限・上限: sum(w) ∈ [1 - cash_max, 1 - cash_min]
    invest_min = 1.0 - float(cfg.cash_bounds[1])
    invest_max = 1.0 - float(cfg.cash_bounds[0])
    # 実現可能性: 銘柄上限と地域上限から投資できる最大合計を下限が超えないように補正
    max_capacity = n * cfg.position_limit
    region_limits = cfg.region_limits or {}
    unique_regions = sorted(set(regions))
    region_to_idx = {r: [i for i, rr in enumerate(regions) if rr == r] for r in unique_regions}
    # 地域ごとの最大投資可能量（銘柄上限×件数と地域上限の小さい方）を合算
    max_by_regions = 0.0
    for r, idx in region_to_idx.items():
        cap_r = float(region_limits.get(r, 1.0))
        max_by_regions += float(min(cap_r, len(idx) * cfg.position_limit))
    effective_invest_min = min(invest_min, max_capacity, max_by_regions)

    constraints = [
        {"type": "ineq", "fun": lambda w, invest_max=invest_max: invest_max - np.sum(w)},  # sum(w) <= invest_max
        {"type": "ineq", "fun": lambda w, invest_min=effective_invest_min: np.sum(w) - invest_min},  # sum(w) >= invest_min (補正後)
    ]
    # 年率ボラ上限（target_vol）: w' Σ w <= target_vol^2
    if cfg.target_vol is not None:
        var_cap = float(cfg.target_vol) ** 2
        constraints.append({
            "type": "ineq",
            "fun": (lambda w, var_cap=var_cap: var_cap - float(np.dot(w, cov.values @ w))),
        })
    # 地域ごとの上限: sum(w[idx]) <= cap_r
    for r, idx in region_to_idx.items():
        cap_r = float(region_limits.get(r, 1.0))
        constraints.append({
            "type": "ineq",
            "fun": (lambda w, idx=idx, cap_r=cap_r: cap_r - float(np.sum(w[idx]))),
        })

    # 目的関数にわずかなペナルティ（数値安定用）
    def penalized_obj(w: np.ndarray) -> float:
        # 目的関数はobjのみ（地域上限は明示制約にて対応）
        return obj(w)

    res = minimize(
        penalized_obj, x0, method="SLSQP", bounds=bounds, constraints=constraints, options={"maxiter": 500}
    )
    w = res.x if res.success else x0
    # 現金に収める
    # 目的上はsum(w)が範囲内になるはずだが、念のためクリップ
    total = float(np.sum(w))
    if total > invest_max + 1e-9:
        # 収縮は地域制約を壊さない
        w = w * (invest_max / total)
    # 総投資の下限方向には後処理で拡大しない（地域上限を壊しうるため）
    return w


