from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import pandas as pd

from ..tools.risk_tool import compute_returns, risk_metrics


@dataclass
class RiskAgent:
    def run(self, price_panels: Dict[str, pd.DataFrame]) -> dict:
        """地域ごとの価格パネルから統合リスク指標を計算。"""
        # price_panels: {region: prices_df}
        combined = None
        for region, prices in price_panels.items():
            if prices is None or prices.empty:
                continue
            if combined is None:
                combined = prices.copy()
            else:
                # outer join to align dates
                combined = combined.join(prices, how="outer", lsuffix="", rsuffix="")

        if combined is None or combined.empty:
            return {"metrics": {}}

        rets = compute_returns(combined, method="pct")
        metrics = risk_metrics(rets)
        return {"metrics": metrics}


