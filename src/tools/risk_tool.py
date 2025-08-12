from __future__ import annotations

import numpy as np
import pandas as pd


def compute_returns(prices: pd.DataFrame, method: str = "log") -> pd.DataFrame:
    prices = prices.sort_index()
    if method == "pct":
        rets = prices.pct_change()
    else:
        rets = np.log(prices / prices.shift(1))
    return rets.dropna(how="all")


def max_drawdown(series: pd.Series) -> float:
    cum = (1 + series.fillna(0)).cumprod()
    peak = cum.cummax()
    dd = (cum / peak) - 1.0
    return float(dd.min())


def risk_metrics(returns_df: pd.DataFrame, trading_days: int = 252) -> dict:
    rets = returns_df.dropna(how="all")
    cov = rets.cov() * trading_days
    corr = rets.corr()
    vol = rets.std() * np.sqrt(trading_days)
    port_dd = {c: max_drawdown(rets[c].fillna(0)) for c in rets.columns}
    return {
        "covariance": cov.to_dict(),
        "correlation": corr.to_dict(),
        "volatility": vol.to_dict(),
        "max_drawdown": port_dd,
    }


