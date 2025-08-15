from __future__ import annotations

from typing import Any, List, Optional

import pandas as pd
import numpy as np
import logging

from ..tools.optimizer_tool import MVConfig, optimize_mean_variance
from ..tools.risk_tool import compute_returns


def optimize_portfolio(
    candidates_by_region: list[dict],
    constraints: dict,
    prices_df: Optional[pd.DataFrame] = None,
) -> dict:
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

    # 価格に存在する銘柄のみに絞り、不足が多い場合は合成価格にフォールバック
    selected_pairs: List[tuple[str, str]] = selected
    all_tickers = [t for t, _ in selected_pairs]
    ticker_to_region = {t: r for t, r in selected_pairs}

    use_synthetic = False
    available_tickers: List[str] = []
    missing_tickers: List[str] = []
    note_flag = ""

    if prices_df is None or prices_df.empty:
        use_synthetic = True
        note_flag = "synthetic returns"
    else:
        available_tickers = [t for t in all_tickers if t in prices_df.columns]
        missing_tickers = sorted(set(all_tickers) - set(available_tickers))
        if missing_tickers:
            head = ", ".join(missing_tickers[:10])
            suffix = "..." if len(missing_tickers) > 10 else ""
            logging.warning(
                f"Missing prices for {len(missing_tickers)} tickers: {head}{suffix}"
            )
        # カバレッジが低い場合は合成にフォールバック（60%未満 または 利用可能が2未満）
        coverage = (len(available_tickers) / max(1, len(all_tickers)))
        if len(available_tickers) < 2 or coverage < 0.6:
            use_synthetic = True
            note_flag = "synthetic returns"

    if use_synthetic:
        tickers = all_tickers
        regions = [ticker_to_region[t] for t in tickers]
        rng = np.random.default_rng(0)
        T = 252
        prices = pd.DataFrame(index=pd.RangeIndex(T))
        for t in tickers:
            rets = rng.normal(0.0003, 0.01, T)
            prices[t] = 100 * (1 + pd.Series(rets)).cumprod()
        rets = prices.pct_change().dropna()
    else:
        tickers = available_tickers
        regions = [ticker_to_region[t] for t in tickers]
        rets = prices_df[tickers].pct_change(fill_method=None).dropna(how="all")
        note_flag = "filtered missing prices"

    mu = rets.mean() * 252
    cov = rets.cov() * 252

    cfg = MVConfig(
        target=constraints.get("target", "min_vol"),
        region_limits=region_limits,
        position_limit=position_limit,
        cash_bounds=(constraints.get("cash_min", 0.0), constraints.get("cash_max", 0.1)),
        risk_aversion=float(constraints.get("risk_aversion", 0.0)),
        target_vol=(float(constraints["target_vol"]) if constraints.get("target_vol") is not None else None),
    )
    w = optimize_mean_variance(tickers, regions, mu, cov, cfg)

    # 最適化に使用した銘柄順で結果を構築
    pairs_for_weights = [(t, ticker_to_region[t]) for t in tickers]
    weights = [
        {"ticker": t, "region": r, "weight": round(float(wi), 6)}
        for (t, r), wi in zip(pairs_for_weights, w)
        if wi > 1e-6
    ]
    cash_weight = round(max(0.0, 1.0 - sum(x["weight"] for x in weights)), 6)

    return {
        "as_of": as_of,
        "region_limits": region_limits,
        "position_limit": position_limit,
        "weights": weights,
        "cash_weight": cash_weight,
        "notes": f"P0 mean-variance ({note_flag})",
    }


