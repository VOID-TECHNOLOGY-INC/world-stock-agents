import numpy as np
import pandas as pd

from src.tools.optimizer_tool import MVConfig, optimize_mean_variance


def test_optimize_mean_variance_bounds_and_sum():
    tickers = ["A", "B", "C"]
    regions = ["US", "US", "JP"]
    mu = pd.Series({"A": 0.08, "B": 0.06, "C": 0.05})
    cov = pd.DataFrame(
        [[0.04, 0.01, 0.0], [0.01, 0.05, 0.0], [0.0, 0.0, 0.03]], index=tickers, columns=tickers
    )
    cfg = MVConfig(target="min_vol", region_limits={"US": 0.5, "JP": 0.5}, position_limit=0.1)
    w = optimize_mean_variance(tickers, regions, mu, cov, cfg)
    assert (w >= -1e-9).all() and (w <= 0.1 + 1e-9).all()
    assert np.sum(w) <= 1.0 + 1e-6

