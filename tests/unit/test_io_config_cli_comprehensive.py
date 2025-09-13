from __future__ import annotations

import os

from src.config import load_config


def test_load_config_defaults(tmp_path, monkeypatch):
    # ensure env not set
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AGENTS_BASE_URL", raising=False)

    outdir = tmp_path / "artifacts"
    cfg = load_config(str(outdir))

    assert cfg.output_dir == str(outdir)
    assert cfg.region_limits == {"US": 0.5, "JP": 0.3, "EU": 0.3, "CN": 0.2}
    assert cfg.position_limit == 0.07
    assert cfg.cash_min == 0.0 and cfg.cash_max == 0.10

    # new defaults
    assert cfg.risk_aversion == 0.0
    assert cfg.target_vol is None
