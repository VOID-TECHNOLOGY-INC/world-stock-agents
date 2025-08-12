from src.agents.macro import MacroAgent


def test_macro_agent_default_weights_sum_to_one():
    agent = MacroAgent()
    weights = agent.propose(region_list=["US", "JP", "EU", "CN"])
    assert set(weights.keys()) == {"US", "JP", "EU", "CN"}
    assert abs(sum(weights.values()) - 1.0) < 1e-6
    for w in weights.values():
        assert 0.0 <= w <= 1.0

