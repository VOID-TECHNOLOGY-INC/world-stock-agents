from __future__ import annotations

import os
from typing import Any, List, Tuple

import pandas as pd
import requests
import json

API_URL = "https://api.perplexity.ai/chat/completions"


def is_perplexity_configured() -> bool:
    """Return True if Perplexity API is configured."""
    return bool(os.environ.get("PPLX_API_KEY"))


def _chat(system: str, user: str, model: str = "pplx-70b-online") -> str:
    if not is_perplexity_configured():
        return ""
    headers = {
        "Authorization": f"Bearer {os.environ['PPLX_API_KEY']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.3,
        "max_tokens": 600,
    }
    try:
        resp = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
    except Exception:
        return ""


def generate_thesis_and_risks(
    ticker: str,
    name: str,
    region: str,
    features: dict[str, Any],
    technical_indicators: dict[str, Any] | None = None,
    news_items: list[dict[str, Any]] | None = None,
    evidence: list[dict[str, Any]] | None = None,
) -> tuple[str, List[str]]:
    """Generate thesis and risks using Perplexity API (Japanese).

    入力を拡充し、JSON出力を推奨して堅牢にパースする。
    """
    system = (
        "あなたは株式アナリストです。事実ベースで簡潔に日本語で回答し、推測は避けます。\n"
        "出力は可能ならJSONで返してください: {\"thesis\": str, \"risks\": [str,...], \"references\": [ {\"url\": str, \"title\": str} ] }\n"
        "thesisは1-2文、risksは最大3件、重複や見出し語は不要です。必要に応じて要点を補足し、全体として過度に短すぎない表現にしてください。"
    )

    lines: list[str] = []
    lines.append(f"ティッカー: {ticker}")
    lines.append(f"名称: {name}")
    lines.append(f"地域: {region}")
    lines.append("ファンダメンタル指標 (0..1 正規化):")
    for k, v in features.items():
        if k != "technical":
            try:
                lines.append(f"- {k}: {float(v):.3f}")
            except Exception:
                lines.append(f"- {k}: {v}")

    if technical_indicators:
        lines.append("\nテクニカル指標:")
        for k, v in technical_indicators.items():
            if v is not None and not pd.isna(v):
                if str(k).startswith("mom_"):
                    try:
                        lines.append(f"- {k}: {float(v):.1%}")
                    except Exception:
                        lines.append(f"- {k}: {v}")
                elif k == "volume_trend":
                    try:
                        lines.append(f"- {k}: {float(v):.2f}")
                    except Exception:
                        lines.append(f"- {k}: {v}")
                else:
                    lines.append(f"- {k}: {v}")
            else:
                lines.append(f"- {k}: N/A")

    if news_items:
        lines.append("\n最近のニュース上位:")
        for n in news_items[:3]:
            title = n.get("title", "")
            url = n.get("url", "")
            dt = n.get("date", "")
            if title and url:
                lines.append(f"- {dt} {title} ({url})")

    if evidence:
        lines.append("\n参考メトリクス:")
        for e in evidence[:3]:
            nm = e.get("name")
            val = e.get("value")
            if nm is not None and val is not None:
                lines.append(f"- {nm}: {val}")

    user = (
        "\n".join(lines)
        + "\n\nこれらの指標とニュースに基づき、投資仮説(thesis)を1-2文で、"
        + "次に主なリスク(risks)を最大3点、箇条書きで提示してください。"
        + "可能ならJSONで返してください。JSONが難しければテキストでも可。"
    )

    text = _chat(system, user)
    if not text:
        return (
            f"{name} は基本指標とモメンタムが相対的に良好。継続成長が見込まれる。",
            ["需給悪化", "規制変更", "マクロ下振れ"],
        )

    # JSONパースを優先
    thesis: str | None = None
    risks: List[str] = []
    content = text.strip()
    try:
        # コードブロックや前後テキストが混じる可能性を考慮し、最初の{...}を抽出
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            json_text = content[start : end + 1]
            obj = json.loads(json_text)
            if isinstance(obj, dict):
                th = obj.get("thesis")
                if isinstance(th, str) and th.strip():
                    thesis = th.strip()
                rk = obj.get("risks")
                if isinstance(rk, list):
                    risks = [str(x).lstrip("- ・* ").strip() for x in rk if str(x).strip()][:3]
    except Exception:
        pass

    if thesis is None:
        # テキストの行分割フォールバック
        lines = [l.strip() for l in content.splitlines() if l.strip()]
        # 見出し行の除去
        lines = [l for l in lines if not (l.startswith("#") or l.endswith(":") or l.endswith("："))]
        thesis = lines[0] if lines else f"{name} は基本指標とモメンタムが相対的に良好。"
        if len(lines) > 1:
            risks = [l.lstrip("- ・* ").strip() for l in lines[1:4]]

    if not risks:
        risks = ["需給悪化", "規制変更", "マクロ下振れ"]

    return thesis, risks[:3]
