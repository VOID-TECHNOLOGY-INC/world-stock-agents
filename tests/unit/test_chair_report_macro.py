from src.agents.chair import build_report


def test_build_report_includes_macro_and_top3():
    candidates = [{
        "region": "US",
        "candidates": [{
            "ticker": "AAPL",
            "thesis": "ok",
            "score_overall": 0.9,
            "score_breakdown": {"fundamental": 0.8, "technical": 0.7, "growth": 0.6, "news": 0.2}
        }]
    }]
    portfolio = {"as_of": "2025-08-12", "weights": [{"ticker": "AAPL", "region": "US", "weight": 0.1}], "cash_weight": 0.9}
    kpi = {"metrics": {"volatility": {"AAPL": 0.2}}}
    macro = {"US": 0.5, "JP": 0.3, "EU": 0.2}
    md = build_report(candidates_all=candidates, portfolio=portfolio, kpi=kpi, macro=macro)
    assert "マクロ概況" in md
    assert "US: 50%" in md
    assert "(score=0.90;" in md


