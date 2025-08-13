from datetime import date
import pandas as pd

from src.agents.regions import RegionAgent


class _NoMarketData:
    def get_prices(self, tickers, lookback_days=260):
        return pd.DataFrame(), pd.DataFrame()


def test_region_agent_falls_back_to_dummy(monkeypatch):
    agent = RegionAgent(name="US", universe="REAL", tools={"marketdata": _NoMarketData()})
    out = agent.run(as_of=date(2025, 8, 12), top_n=5)
    assert out.get("region") == "US"
    assert len(out.get("candidates", [])) == 5


