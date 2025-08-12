from __future__ import annotations

import os
from typing import Any, List, Tuple

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dependency at runtime
    OpenAI = None  # type: ignore


def is_openai_configured() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY")) and OpenAI is not None


def _chat(system: str, user: str, model: str = "gpt-4o-mini") -> str:
    if not is_openai_configured():
        return ""
    client = OpenAI()
    # Try Responses API (Agents SDK相当) → fallback to Chat Completions
    try:
        resp = client.responses.create(
            model=model,
            input=[
                {
                    "role": "system",
                    "content": [{"type": "text", "text": system}],
                },
                {"role": "user", "content": [{"type": "text", "text": user}]},
            ],
            temperature=0.3,
        )
        # responses API: output_text helper may exist; otherwise compose
        if hasattr(resp, "output_text") and callable(getattr(resp, "output_text")):
            text = resp.output_text
            return text if isinstance(text, str) else str(text)
        # generic extraction
        for item in getattr(resp, "output", []) or []:
            if item.get("type") == "message":
                parts = item.get("content", [])
                for p in parts:
                    if p.get("type") == "output_text":
                        return p.get("text", "")
        # as a last resort, return stringified
        return str(resp)
    except Exception:
        pass
    # Fallback
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.3,
        )
        return resp.choices[0].message.content or ""
    except Exception:
        return ""


def generate_thesis_and_risks(
    ticker: str,
    name: str,
    region: str,
    features: dict[str, Any],
) -> tuple[str, list[str]]:
    """特徴量のサマリから thesis と risks を生成（日本語）。"""
    system = (
        "あなたは株式アナリストです。事実ベースで簡潔に日本語で回答し、推測は避けます。"
    )
    lines = [
        f"ティッカー: {ticker}",
        f"名称: {name}",
        f"地域: {region}",
        "特徴量 (0..1 正規化):",
    ]
    for k, v in features.items():
        lines.append(f"- {k}: {v}")
    user = (
        "\n".join(lines)
        + "\n\n1-2文で投資仮説(thesis)を記述し、その後に最大3点の主なリスク(risks)を箇条書きで提示してください。"
    )

    text = _chat(system, user)
    if not text:
        return (
            f"{name} は基本指標とモメンタムが相対的に良好。継続成長が見込まれる。",
            ["需給悪化", "規制変更", "マクロ下振れ"],
        )
    # 簡易パース: 最初の段落をthesis、ハイフン行をrisksとみなす
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    thesis = lines[0]
    risks: List[str] = [l.lstrip("- ・* ") for l in lines[1:4]] if len(lines) > 1 else []
    if not risks:
        risks = ["需給悪化", "規制変更", "マクロ下振れ"]
    return thesis, risks[:3]


def generate_report_markdown(
    candidates_all: list[dict], portfolio: dict, max_per_region: int = 3
) -> str:
    system = (
        "あなたはポートフォリオマネージャーの議長です。日本語で明瞭なMarkdownレポートを書きます。"
    )
    # 入力を短く整形
    lines: list[str] = []
    lines.append("ポートフォリオ:")
    for w in portfolio.get("weights", [])[:30]:
        lines.append(f"- {w['ticker']} ({w['region']}): {w['weight']:.2%}")
    lines.append(f"- Cash: {portfolio.get('cash_weight', 0.0):.2%}")
    lines.append("\n候補:")
    for region_blob in candidates_all:
        region = region_blob.get("region")
        lines.append(f"[{region}] 上位")
        for c in region_blob.get("candidates", [])[:max_per_region]:
            lines.append(
                f"- {c['ticker']}: score={c['score_overall']:.2f}, thesis={c.get('thesis','')}"
            )
    user = (
        "\n".join(lines)
        + "\n\n以下の構成でMarkdownを生成: 1.サマリー 2.地域別ハイライト 3.最終ポートフォリオ（表）"
    )
    md = _chat(system, user)
    return md


