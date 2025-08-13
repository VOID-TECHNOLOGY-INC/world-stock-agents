import pandas as pd

from src.agents.macro import MacroAgent


def test_macro_agent_reads_csv_and_normalizes(tmp_path):
    p = tmp_path / "macro.csv"
    pd.DataFrame({"region": ["US", "JP"], "weight": [2.0, 1.0]}).to_csv(p, index=False)
    agent = MacroAgent(csv_path=str(p))
    w = agent.propose(["US", "JP"])
    # 比率2:1 -> 正規化で US=0.666..., JP=0.333...
    assert abs(w["US"] - (2/3)) < 1e-6
    assert abs(w["JP"] - (1/3)) < 1e-6


def test_macro_agent_fallback_to_default_on_error(tmp_path):
    # 不正CSV: 列がない
    p = tmp_path / "bad.csv"
    pd.DataFrame({"x": [1]}).to_csv(p, index=False)
    agent = MacroAgent(csv_path=str(p))
    w = agent.propose(["US", "JP"])
    assert set(w.keys()) == {"US", "JP"}
    assert abs(sum(w.values()) - 1.0) < 1e-6

