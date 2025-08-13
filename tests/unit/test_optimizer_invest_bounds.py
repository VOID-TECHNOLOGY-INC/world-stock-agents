import numpy as np
import pandas as pd

from src.tools.optimizer_tool import MVConfig, optimize_mean_variance


def test_optimizer_enforces_investment_bounds():
    # 十分な銘柄数で投資下限を満たせる設定
    tickers = [f"T{i}" for i in range(10)]
    regions = ["US"] * 10
    # Simple covariance matrix
    cov = pd.DataFrame(
        0.02 * np.eye(len(tickers)), index=tickers, columns=tickers
    )
    mu = pd.Series({t: 0.08 for t in tickers})

    # Require to invest between 90% and 100% (cash 0-10%)
    cfg = MVConfig(
        target="min_vol",
        region_limits=None,
        position_limit=0.2,
        cash_bounds=(0.0, 0.1),
    )

    w = optimize_mean_variance(tickers, regions, mu, cov, cfg)
    s = float(np.sum(w))
    assert 0.9 - 1e-6 <= s <= 1.0 + 1e-6
    assert (w >= -1e-9).all() and (w <= cfg.position_limit + 1e-9).all()


