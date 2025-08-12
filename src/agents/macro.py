from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class MacroAgent:
    """簡易ルールベース: 当面は固定の初期重みを返す。後続で為替・金利・商品を反映。
    例: US 45%, JP 25%, EU 20%, CN 10%
    """

    def propose(self, region_list: List[str]) -> Dict[str, float]:
        base = {"US": 0.45, "JP": 0.25, "EU": 0.20, "CN": 0.10}
        # 指定地域以外は0、残りは正規化
        filt = {r: base.get(r, 0.0) for r in region_list}
        s = sum(filt.values()) or 1.0
        return {r: v / s for r, v in filt.items()}


