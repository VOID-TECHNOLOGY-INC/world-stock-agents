from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import List

import typer
from rich import print

from .config import load_config
from .io.writers import ensure_output_dir, write_json, write_text
from .agents.regions import RegionAgent
from .agents.chair import build_report
from .agents.optimizer import optimize_portfolio
from .tools.marketdata import MarketDataClient


app = typer.Typer(add_completion=False, no_args_is_help=True)


def _parse_date(d: str) -> date:
    return datetime.strptime(d, "%Y-%m-%d").date()


@app.command()
def candidates(
    regions: str = typer.Option("JP,US", help="対象地域 (CSV)"),
    run_date: str = typer.Option(datetime.today().strftime("%Y-%m-%d"), "--date"),
    output: str = typer.Option("./artifacts", help="出力先ディレクトリ"),
    top_n: int = typer.Option(50, help="各地域の上位候補数"),
):
    """地域別エージェントを実行し、候補JSONを出力する。"""
    as_of = _parse_date(run_date)
    cfg = load_config(output)
    ensure_output_dir(cfg.output_dir)

    region_list = [r.strip().upper() for r in regions.split(",") if r.strip()]
    print(f"[bold]Regions:[/bold] {region_list}  Date: {as_of}")

    results: List[dict] = []
    for region in region_list:
        agent = RegionAgent(name=region, universe="REAL", tools={"marketdata": MarketDataClient()})
        out = agent.run(as_of=as_of, top_n=top_n)
        results.append(out)
        out_path = Path(cfg.output_dir) / f"candidates_{region}_{as_of.strftime('%Y%m%d')}.json"
        write_json(out_path, out)
        print(f"✅ candidates saved: {out_path}")

    print("done.")


@app.command()
def report(
    input: str = typer.Option(..., help="最終ポートフォリオJSONのパス"),
    output: str = typer.Option("./artifacts", help="出力先ディレクトリ"),
):
    """最終ポートフォリオからMarkdownレポートを生成。"""
    cfg = load_config(output)
    ensure_output_dir(cfg.output_dir)

    with open(input, "r", encoding="utf-8") as f:
        portfolio = json.load(f)

    md = build_report(candidates_all=[], portfolio=portfolio, kpi={})
    as_of = portfolio.get("as_of", datetime.today().strftime("%Y-%m-%d"))
    out_md = Path(cfg.output_dir) / f"report_{as_of.replace('-', '')}.md"
    write_text(out_md, md)
    print(f"✅ report saved: {out_md}")


@app.command()
def run(
    regions: str = typer.Option("JP,US", help="対象地域 (CSV)"),
    run_date: str = typer.Option(datetime.today().strftime("%Y-%m-%d"), "--date"),
    output: str = typer.Option("./artifacts", help="出力先ディレクトリ"),
    top_n: int = typer.Option(50, help="各地域の上位候補数"),
):
    """週次エンドツーエンド実行。候補→最適化→レポ出力。"""
    as_of = _parse_date(run_date)
    cfg = load_config(output)
    ensure_output_dir(cfg.output_dir)

    region_list = [r.strip().upper() for r in regions.split(",") if r.strip()]
    print(f"[bold]Run weekly[/bold] regions={region_list} date={as_of}")

    candidates_all: List[dict] = []
    for region in region_list:
        agent = RegionAgent(name=region, universe="REAL", tools={"marketdata": MarketDataClient()})
        out = agent.run(as_of=as_of, top_n=top_n)
        candidates_all.append(out)
        out_path = Path(cfg.output_dir) / f"candidates_{region}_{as_of.strftime('%Y%m%d')}.json"
        write_json(out_path, out)

    portfolio = optimize_portfolio(
        candidates_by_region=candidates_all,
        constraints={
            "region_limits": cfg.region_limits,
            "position_limit": cfg.position_limit,
            "cash_min": cfg.cash_min,
            "cash_max": cfg.cash_max,
            "as_of": as_of.strftime("%Y-%m-%d"),
        },
    )

    port_path = Path(cfg.output_dir) / f"portfolio_{as_of.strftime('%Y%m%d')}.json"
    write_json(port_path, portfolio)
    print(f"✅ portfolio saved: {port_path}")

    md = build_report(candidates_all=candidates_all, portfolio=portfolio, kpi={})
    out_md = Path(cfg.output_dir) / f"report_{as_of.strftime('%Y%m%d')}.md"
    write_text(out_md, md)
    print(f"✅ report saved: {out_md}")


if __name__ == "__main__":
    app()


