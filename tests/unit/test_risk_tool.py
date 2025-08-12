import numpy as np
import pandas as pd

from src.tools.risk_tool import compute_returns, risk_metrics, max_drawdown


def test_compute_returns_pct_change_no_fill():
    idx = pd.date_range("2024-01-01", periods=5, freq="D")
    prices = pd.DataFrame({"A": [100, 101, np.nan, 103, 104]}, index=idx)
    rets = compute_returns(prices, method="pct")
    # 欠損は埋めず、先頭と欠損直後はNaN。02日と05日に値が付くため2行のみ残る。
    assert rets.shape[0] == 2
    assert rets["A"].notna().sum() == 2


def test_risk_metrics_shapes():
    rng = np.random.default_rng(0)
    idx = pd.date_range("2024-01-01", periods=252, freq="B")
    rets = pd.DataFrame({
        "A": rng.normal(0.0003, 0.01, len(idx)),
        "B": rng.normal(0.0002, 0.012, len(idx)),
    }, index=idx)
    met = risk_metrics(rets)
    assert set(met.keys()) == {"covariance", "correlation", "volatility", "max_drawdown"}
    assert set(met["volatility"].keys()) == {"A", "B"}


def test_max_drawdown_negative():
    s = pd.Series([0.1, -0.05, -0.1, 0.02])
    dd = max_drawdown(s)
    assert dd <= 0.0

