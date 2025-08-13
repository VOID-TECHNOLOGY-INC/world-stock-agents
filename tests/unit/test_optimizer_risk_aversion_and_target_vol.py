import numpy as np
import pandas as pd

from src.tools.optimizer_tool import MVConfig, optimize_mean_variance


def test_risk_aversion_increases_expected_return():
    tickers = ["A", "B", "C"]
    regions = ["US", "US", "US"]
    mu = pd.Series({"A": 0.05, "B": 0.08, "C": 0.15})
    cov = pd.DataFrame(
        [[0.04, 0.005, 0.01], [0.005, 0.06, 0.015], [0.01, 0.015, 0.09]],
        index=tickers,
        columns=tickers,
    )

    cfg_low = MVConfig(position_limit=1.0, cash_bounds=(0.0, 0.0), risk_aversion=0.0)
    w_low = optimize_mean_variance(tickers, regions, mu, cov, cfg_low)
    ret_low = float(np.dot(w_low, mu.values))

    cfg_high = MVConfig(position_limit=1.0, cash_bounds=(0.0, 0.0), risk_aversion=5.0)
    w_high = optimize_mean_variance(tickers, regions, mu, cov, cfg_high)
    ret_high = float(np.dot(w_high, mu.values))

    assert ret_high > ret_low + 1e-6


def test_target_vol_cap_is_respected():
    tickers = ["A", "B"]
    regions = ["US", "US"]
    mu = pd.Series({"A": 0.15, "B": 0.12})
    cov = pd.DataFrame(np.diag([0.09, 0.09]), index=tickers, columns=tickers)

    cfg = MVConfig(position_limit=1.0, cash_bounds=(0.0, 0.0), risk_aversion=5.0, target_vol=0.22)
    w = optimize_mean_variance(tickers, regions, mu, cov, cfg)

    portfolio_var = float(np.dot(w, cov.values @ w))
    assert portfolio_var <= 0.22**2 + 1e-6
    assert (w >= -1e-9).all()

