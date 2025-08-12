from __future__ import annotations

from typing import Any, List

import pandas as pd
import numpy as np

from ..tools.optimizer_tool import MVConfig, optimize_mean_variance
from ..tools.risk_tool import compute_returns


def optimize_portfolio(candidates_by_region: list[dict], constraints: dict) -> dict:
    """Mean-Variance 最適化（P0）。

    前処理: 各地域の候補上位から対象銘柄を選定（position_limitを満たす最大数）
    単純に過去リターンの平均/共分散を推定してMV最適化。
    """
    region_limits: dict[str, float] = constraints.get("region_limits", {})
    position_limit: float = float(constraints.get("position_limit", 0.07))
    as_of: str = constraints.get("as_of")

    # ティッカーと地域の収集
    selected: List[tuple[str, str]] = []
    for region_blob in candidates_by_region:
        region = region_blob["region"]
        limit = float(region_limits.get(region, 0.25))
        candidates = region_blob.get("candidates", [])
        if not candidates:
            continue
        max_positions = max(1, int(limit / position_limit))
        take = min(max_positions, len(candidates))
        for c in candidates[:take]:
            selected.append((c["ticker"], region))

    if not selected:
        return {"as_of": as_of, "weights": [], "cash_weight": 1.0, "notes": "no selection"}

    tickers = [t for t, _ in selected]
    regions = [r for _, r in selected]

    # 簡易に returns を合成するため、銘柄ごとにダミー系列を生成（将来: 実価格から推定）
    # ここでは安定動作のためランダムウォーク近似を用いる（将来、価格パイプを受け取る構造に変更）
    rng = np.random.default_rng(0)
    T = 252
    prices = pd.DataFrame(index=pd.RangeIndex(T))
    for t in tickers:
        rets = rng.normal(0.0003, 0.01, T)
        prices[t] = 100 * (1 + pd.Series(rets)).cumprod()
    rets = prices.pct_change().dropna()

    mu = rets.mean() * 252
    cov = rets.cov() * 252

    cfg = MVConfig(
        target="min_vol",
        region_limits=region_limits,
        position_limit=position_limit,
        cash_bounds=(constraints.get("cash_min", 0.0), constraints.get("cash_max", 0.1)),
    )
    w = optimize_mean_variance(tickers, regions, mu, cov, cfg)

    weights = [
        {"ticker": t, "region": r, "weight": round(float(wi), 6)}
        for (t, r), wi in zip(selected, w)
        if wi > 1e-6
    ]
    cash_weight = round(max(0.0, 1.0 - sum(x["weight"] for x in weights)), 6)

    return {
        "as_of": as_of,
        "region_limits": region_limits,
        "position_limit": position_limit,
        "weights": weights,
        "cash_weight": cash_weight,
        "notes": "P0 mean-variance (synthetic returns)",
    }


