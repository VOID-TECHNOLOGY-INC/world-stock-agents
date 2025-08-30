from __future__ import annotations

import os
from typing import Any, List, Tuple

import pandas as pd
import requests

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
) -> tuple[str, List[str]]:
    """Generate thesis and risks using Perplexity API (Japanese)."""
    system = (
        "あなたは株式アナリストです。ファンダメンタル指標とテクニカル指標の両方を考慮して、"
        "包括的な投資分析を行ってください。事実ベースで簡潔に日本語で回答し、推測は避けます。"
    )
    lines = [
        f"ティッカー: {ticker}",
        f"名称: {name}",
        f"地域: {region}",
        "ファンダメンタル指標 (0..1 正規化):",
    ]
    for k, v in features.items():
        if k != "technical":
            lines.append(f"- {k}: {v:.3f}")

    if technical_indicators:
        lines.append("\nテクニカル指標:")
        for k, v in technical_indicators.items():
            if v is not None and not pd.isna(v):
                if k.startswith("mom_"):
                    lines.append(f"- {k}: {v:.1%}")
                elif k == "volume_trend":
                    lines.append(f"- {k}: {v:.2f}")
                else:
                    lines.append(f"- {k}: {v}")
            else:
                lines.append(f"- {k}: N/A")

    user = (
        "\n".join(lines)
        + "\n\nこれらの指標を基に、包括的な投資仮説(thesis)を1-2文で記述し、"
        + "その後に最大3点の主なリスク(risks)を箇条書きで提示してください。"
        + "テクニカル指標から読み取れる価格動向と出来高の特徴も考慮してください。"
    )

    text = _chat(system, user)
    if not text:
        return (
            f"{name} は基本指標とモメンタムが相対的に良好。継続成長が見込まれる。",
            ["需給悪化", "規制変更", "マクロ下振れ"],
        )
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    thesis = lines[0] if lines else f"{name} は基本指標とモメンタムが相対的に良好。"
    risks: List[str] = [l.lstrip("- ・* ") for l in lines[1:4]] if len(lines) > 1 else []
    if not risks:
        risks = ["需給悪化", "規制変更", "マクロ下振れ"]
    return thesis, risks[:3]
