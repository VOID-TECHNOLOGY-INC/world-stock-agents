from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AppConfig:
    openai_api_key: Optional[str]
    agents_base_url: Optional[str]
    output_dir: str

    # Limits and rules (MVP defaults per spec)
    region_limits: dict[str, float]
    position_limit: float
    cash_min: float
    cash_max: float

    # Optimization knobs (defaults)
    risk_aversion: float
    target_vol: Optional[float]


def load_config(output_dir: str) -> AppConfig:
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    agents_base_url = os.environ.get("AGENTS_BASE_URL")

    # Defaults from spec 11
    region_limits = {"US": 0.5, "JP": 0.3, "EU": 0.3, "CN": 0.2}
    position_limit = 0.07
    cash_min, cash_max = 0.0, 0.10

    return AppConfig(
        openai_api_key=openai_api_key,
        agents_base_url=agents_base_url,
        output_dir=output_dir,
        region_limits=region_limits,
        position_limit=position_limit,
        cash_min=cash_min,
        cash_max=cash_max,
        risk_aversion=0.0,
        target_vol=None,
    )


