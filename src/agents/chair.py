from __future__ import annotations

from typing import Any
from .openai_agent import is_openai_configured, generate_report_markdown


def build_report(candidates_all: list[dict], portfolio: dict, kpi: dict) -> str:
    # シンプルなMarkdown出力（MVP）
    as_of = portfolio.get("as_of", "")
    if is_openai_configured():
        md = generate_report_markdown(candidates_all=candidates_all, portfolio=portfolio)
        if md:
            return md

    # フォールバック（固定テンプレ）
    lines: list[str] = []
    lines.append(f"# 週次レポート ({as_of})")
    lines.append("")
    lines.append("## サマリー")
    lines.append("- 配分: 最終ポートフォリオを参照")
    lines.append("")

    lines.append("## 地域別ハイライト")
    for region_blob in candidates_all:
        region = region_blob.get("region")
        lines.append(f"### {region}")
        for c in region_blob.get("candidates", [])[:3]:
            lines.append(f"- {c['ticker']}: {c['thesis']} (score={c['score_overall']:.2f})")
        lines.append("")

    lines.append("## 最終ポートフォリオ")
    lines.append("ticker | region | weight")
    lines.append(":--|:--:|--:")
    for w in portfolio.get("weights", []):
        lines.append(f"{w['ticker']} | {w['region']} | {w['weight']:.2%}")
    lines.append(f"Cash | - | {portfolio.get('cash_weight', 0.0):.2%}")

    return "\n".join(lines)


