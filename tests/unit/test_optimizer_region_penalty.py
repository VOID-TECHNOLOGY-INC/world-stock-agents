import numpy as np
import pandas as pd

from src.tools.optimizer_tool import MVConfig, optimize_mean_variance


def test_region_penalty_limits_sum_weight_per_region():
    tickers = ["A", "B", "C", "D"]
    regions = ["US", "US", "JP", "JP"]
    # 単純な共分散（ほぼ単位行列）
    cov = pd.DataFrame(np.eye(4), index=tickers, columns=tickers)
    mu = pd.Series([0.1, 0.1, 0.1, 0.1], index=tickers)
    cfg = MVConfig(target="max_return", region_limits={"US": 0.2, "JP": 0.6}, position_limit=0.6, cash_bounds=(0.0, 0.0))
    w = optimize_mean_variance(tickers, regions, mu, cov, cfg)
    us_sum = float(w[0] + w[1])
    jp_sum = float(w[2] + w[3])
    assert us_sum <= 0.2 + 1e-3
    assert jp_sum <= 0.6 + 1e-3


