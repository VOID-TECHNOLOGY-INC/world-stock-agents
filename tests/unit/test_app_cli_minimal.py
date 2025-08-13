import os
from pathlib import Path

import typer
from typer.testing import CliRunner

from src.app import app


def test_cli_run_generates_artifacts(tmp_path, monkeypatch):
    runner = CliRunner()
    outdir = tmp_path / "artifacts"

    # RegionAgent 内部のMarketDataClientが実データに触れないように環境を固定
    os.environ.pop("OPENAI_API_KEY", None)

    # マクロCSV（テスト用）を用意
    import pandas as pd
    outdir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"region": ["JP"], "weight": [1.0]}).to_csv(outdir / "macro.csv", index=False)

    result = runner.invoke(
        app,
        [
            "run",
            "--regions",
            "JP",
            "--date",
            "2025-08-12",
            "--output",
            str(outdir),
            "--top-n",
            "10",
            "--macro-csv",
            str(outdir / "macro.csv"),
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    # 主要成果物が生成されていること
    as_of = "20250812"
    assert (outdir / f"portfolio_{as_of}.json").exists()
    assert (outdir / f"report_{as_of}.md").exists()
    assert (outdir / f"candidates_JP_{as_of}.json").exists()
    assert (outdir / f"growth_JP_{as_of}.json").exists()


