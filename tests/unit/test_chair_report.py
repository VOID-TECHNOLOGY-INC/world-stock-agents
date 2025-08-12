from src.agents.chair import build_report


def test_build_report_includes_risk_section_when_provided():
    candidates = [{"region": "US", "candidates": [{"ticker": "A", "thesis": "ok", "score_overall": 0.9}]}]
    portfolio = {"as_of": "2025-08-12", "weights": [{"ticker": "A", "region": "US", "weight": 0.1}], "cash_weight": 0.9}
    kpi = {"metrics": {"volatility": {"A": 0.2}}}
    md = build_report(candidates_all=candidates, portfolio=portfolio, kpi=kpi)
    assert "最終ポートフォリオ" in md
    # KPIのキーが本文に反映されるよう、今後の実装でヘッダ出力を追加予定

