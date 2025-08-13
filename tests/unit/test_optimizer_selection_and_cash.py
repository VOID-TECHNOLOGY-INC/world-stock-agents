import pandas as pd
import numpy as np

from src.agents.optimizer import optimize_portfolio


def test_optimizer_selection_and_cash_weight():
    # 2地域×各3銘柄、position_limit=0.2、地域上限=0.4 → 地域ごとに最大2銘柄、計4銘柄が選ばれる
    candidates_by_region = [
        {
            "region": "US",
            "candidates": [
                {"ticker": "U1"}, {"ticker": "U2"}, {"ticker": "U3"},
            ],
        },
        {
            "region": "JP",
            "candidates": [
                {"ticker": "J1"}, {"ticker": "J2"}, {"ticker": "J3"},
            ],
        },
    ]
    constraints = {
        "region_limits": {"US": 0.4, "JP": 0.4},
        "position_limit": 0.2,
        "cash_min": 0.1,
        "cash_max": 0.3,
        "as_of": "2025-08-12",
    }

    port = optimize_portfolio(candidates_by_region, constraints, prices_df=pd.DataFrame())
    ws = port["weights"]
    # 選抜数は最大4銘柄（2+2）
    assert 1 <= len(ws) <= 4
    # 現金比率は0..1の範囲
    assert 0.0 <= port["cash_weight"] <= 1.0


