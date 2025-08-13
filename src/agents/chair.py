from __future__ import annotations

from typing import Any, Dict, Optional
from .openai_agent import is_openai_configured, generate_report_markdown


def build_report(
    candidates_all: list[dict],
    portfolio: dict,
    kpi: dict,
    macro: Optional[Dict[str, float]] = None,
    use_ai: bool = False,
    images: Optional[Dict[str, str]] = None,
) -> str:
    # シンプルなMarkdown出力（MVP）
    as_of = portfolio.get("as_of", "")
    if use_ai and is_openai_configured():
        md = generate_report_markdown(candidates_all=candidates_all, portfolio=portfolio)
        if md:
            return md

    # フォールバック（固定テンプレ）
    lines: list[str] = []
    lines.append(f"# 週次レポート ({as_of})")
    lines.append("")
    lines.append("## サマリー")
    lines.append("- 配分: 最終ポートフォリオを参照")
    if macro:
        lines.append("- マクロ: 地域初期重みを参照（下記）")
    lines.append("")

    if macro:
        lines.append("## マクロ概況")
        for r, w in macro.items():
            lines.append(f"- {r}: {w:.0%}")
        lines.append("")

    lines.append("## 地域別ハイライト")
    for region_blob in candidates_all:
        region = region_blob.get("region")
        lines.append(f"### {region}")
        for c in region_blob.get("candidates", [])[:3]:
            sb = c.get("score_breakdown", {}) or {}
            # 上位3指標
            top3 = sorted(sb.items(), key=lambda kv: kv[1], reverse=True)[:3]
            reasons = ", ".join([f"{k}={v:.2f}" for k, v in top3]) if top3 else "-"
            lines.append(
                f"- {c['ticker']}: {c['thesis']} (score={c.get('score_overall', 0.0):.2f}; {reasons})"
            )
        lines.append("")

    lines.append("## 最終ポートフォリオ")
    lines.append("ticker | region | weight")
    lines.append(":--|:--:|--:")
    for w in portfolio.get("weights", []):
        lines.append(f"{w['ticker']} | {w['region']} | {w['weight']:.2%}")
    lines.append(f"Cash | - | {portfolio.get('cash_weight', 0.0):.2%}")

    # 図表の埋め込み（生成済みの画像パスが渡された場合）
    if images:
        lines.append("")
        lines.append("## 図表")
        if images.get("allocation_pie"):
            lines.append(f"![配分円グラフ]({images['allocation_pie']})")
        if images.get("correlation_heatmap"):
            lines.append(f"![相関ヒートマップ]({images['correlation_heatmap']})")

    # 簡易: リスク指標の存在をヘッダで示す
    if kpi and isinstance(kpi, dict) and kpi.get("metrics"):
        lines.append("")
        lines.append("## リスク指標 (概要)")
        met = kpi.get("metrics", {})
        keys = [k for k in ("volatility", "max_drawdown") if k in met]
        if keys:
            lines.append("- Included: " + ", ".join(keys))

    return "\n".join(lines)


def save_correlation_heatmap(correlation: Any, out_path: str) -> None:
    try:
        import pandas as pd  # type: ignore
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        return
    # dict -> DataFrame
    if isinstance(correlation, dict):
        try:
            corr_df = pd.DataFrame(correlation)
        except Exception:
            return
    else:
        corr_df = correlation
    if corr_df is None or getattr(corr_df, "empty", True):
        return
    labels = list(corr_df.columns)
    n = len(labels)
    fig_w = min(max(n * 0.3, 6.0), 14.0)
    fig_h = fig_w
    plt.figure(figsize=(fig_w, fig_h))
    plt.imshow(corr_df.values, cmap="coolwarm", vmin=-1, vmax=1)
    plt.colorbar(fraction=0.046, pad=0.04)
    plt.xticks(ticks=range(n), labels=labels, rotation=90, fontsize=6)
    plt.yticks(ticks=range(n), labels=labels, fontsize=6)
    plt.tight_layout()
    try:
        plt.savefig(out_path, dpi=150)
    finally:
        plt.close()


def save_allocation_pie(portfolio: dict, out_path: str) -> None:
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        return
    # 地域別配分 + 現金
    region_weights: Dict[str, float] = {}
    for w in portfolio.get("weights", []) or []:
        r = w.get("region", "-")
        region_weights[r] = region_weights.get(r, 0.0) + float(w.get("weight", 0.0))
    cash = float(portfolio.get("cash_weight", 0.0))
    if cash > 0:
        region_weights["Cash"] = cash
    if not region_weights:
        return
    labels = list(region_weights.keys())
    sizes = list(region_weights.values())
    plt.figure(figsize=(6, 6))
    plt.pie(sizes, labels=labels, autopct="%1.1f%%", startangle=90, counterclock=False)
    plt.tight_layout()
    try:
        plt.savefig(out_path, dpi=150)
    finally:
        plt.close()


