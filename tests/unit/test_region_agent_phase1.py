from datetime import date
from unittest.mock import patch
import pandas as pd

from src.agents.regions import RegionAgent


def _make_prices_volumes(tickers: list[str]):
	# 2銘柄×40営業日のダミー価格・出来高
	idx = pd.date_range("2025-07-01", periods=40, freq="B")
	prices = pd.DataFrame(index=idx, data={
		tickers[0]: pd.Series(range(100, 140), index=idx),
		tickers[1]: pd.Series(range(120, 160), index=idx),
	})
	volumes = pd.DataFrame(index=idx, data={
		tickers[0]: pd.Series([1_000_000 + i*1000 for i in range(40)], index=idx),
		tickers[1]: pd.Series([900_000 + i*800 for i in range(40)], index=idx),
	})
	return prices, volumes


def test_region_agent_uses_fundamentals_and_news_to_update_scores():
	"""FundamentalsとNewsがマージされ、fundamental/newsが0.5固定から変化することを検証"""
	tickers = ["AAA", "BBB"]
	universe_df = pd.DataFrame({"ticker": tickers, "name": ["Alpha", "Beta"]})
	prices, volumes = _make_prices_volumes(tickers)

	# Fundamentals: roic/fcf_marginに差をつける（normalizeで0.5以外になるよう2値に）
	fund_df = pd.DataFrame({
		"ticker": tickers,
		"roic": [0.30, 0.10],
		"fcf_margin": [0.20, 0.05],
		"revenue_cagr": [0.10, 0.00],
		"eps_growth": [0.20, -0.10],
	})

	# News: AAAに好材料、BBBに悪材料
	news_items = [
		{"ticker": "AAA", "title": "Company beats estimates and raises guidance", "url": "http://x", "date": "2025-08-10"},
		{"ticker": "BBB", "title": "Company misses estimates and cuts outlook", "url": "http://y", "date": "2025-08-10"},
	]

	agent = RegionAgent("US", "REAL", tools={})

	with (
		patch("src.agents.regions.load_universe", return_value=universe_df),
		patch("src.agents.regions.MarketDataClient.get_prices", return_value=(prices, volumes)),
		patch("src.agents.regions.FundamentalsClient.get_fundamentals", return_value=fund_df),
		patch("src.agents.regions.NewsClient.get_news", return_value=news_items),
		patch("src.agents.openai_agent.is_openai_configured", return_value=False),
	):
		out = agent.run(date(2025, 8, 15), top_n=2)

	# 出力取得
	cands = out["candidates"]
	assert len(cands) == 2

	# fundamental/newsが0.5固定でないことを検証（両銘柄のどちらかは0.5以外になる）
	fund_vals = [c["score_breakdown"]["fundamental"] for c in cands]
	news_vals = [c["score_breakdown"]["news"] for c in cands]

	assert any(abs(v - 0.5) > 1e-9 for v in fund_vals), f"fundamentalが全て0.5: {fund_vals}"
	assert any(abs(v - 0.5) > 1e-9 for v in news_vals), f"newsが全て0.5: {news_vals}"
