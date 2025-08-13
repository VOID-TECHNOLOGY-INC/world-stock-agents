import pandas as pd
from datetime import date

from src.agents.risk import RiskAgent


def test_risk_agent_merges_panels_and_handles_empty():
    # JPとUSのパネルをouter joinしてメトリクス生成
    idx = pd.date_range("2025-07-01", periods=5, freq="D")
    jp = pd.DataFrame({"J1": [1, 1.01, 1.02, 1.03, 1.04]}, index=idx)
    us = pd.DataFrame({"U1": [1, 0.99, 1.00, 1.02, 1.01]}, index=idx)
    agent = RiskAgent()
    out = agent.run(price_panels={"JP": jp, "US": us})
    assert isinstance(out.get("metrics"), dict) and out["metrics"].get("volatility")

    # 全て空なら空メトリクス
    out2 = agent.run(price_panels={"JP": pd.DataFrame(), "US": pd.DataFrame()})
    assert out2 == {"metrics": {}}


