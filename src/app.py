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
from .agents.risk import RiskAgent
from .agents.macro import MacroAgent
from .tools.risk_tool import compute_returns


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
        # 成長候補を別ファイルに保存
        growth_out_path = Path(cfg.output_dir) / f"growth_{region}_{as_of.strftime('%Y%m%d')}.json"
        write_json(
            growth_out_path,
            {
                "region": region,
                "as_of": as_of.strftime("%Y-%m-%d"),
                "universe": out.get("universe", "REAL"),
                "candidates": out.get("growth_candidates", []),
            },
        )
        print(f"✅ growth saved: {growth_out_path}")

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
    risk_aversion: float = typer.Option(0.0, help="リスク許容度（大きいほどリターン重視）。0でボラ最小。"),
    target_vol: float = typer.Option(None, help="年率ボラ上限（例: 0.18）。未指定で制約なし。"),
    target: str = typer.Option("min_vol", help="目的関数: min_vol / max_return（risk_aversion>0 ならトレードオフ）。"),
    macro_csv: str = typer.Option(None, help="マクロ初期重みCSVのパス（region,weight）。未指定でデフォルト重み。"),
):
    """週次エンドツーエンド実行。候補→最適化→レポ出力。"""
    as_of = _parse_date(run_date)
    cfg = load_config(output)
    ensure_output_dir(cfg.output_dir)

    region_list = [r.strip().upper() for r in regions.split(",") if r.strip()]
    print(f"[bold]Run weekly[/bold] regions={region_list} date={as_of}")

    # macro: 地域初期重み（参考）
    macro_agent = MacroAgent(csv_path=macro_csv)
    macro_weights = macro_agent.propose(region_list)

    candidates_all: List[dict] = []
    region_prices: dict[str, "pd.DataFrame"] = {}
    for region in region_list:
        agent = RegionAgent(name=region, universe="REAL", tools={"marketdata": MarketDataClient()})
        out = agent.run(as_of=as_of, top_n=top_n)
        candidates_all.append(out)
        out_path = Path(cfg.output_dir) / f"candidates_{region}_{as_of.strftime('%Y%m%d')}.json"
        write_json(out_path, out)
        # 価格を再取得（最適化/リスク用）：エージェント内部のMarketDataと同等取得
        # 成長候補を別ファイルに保存
        growth_out_path = Path(cfg.output_dir) / f"growth_{region}_{as_of.strftime('%Y%m%d')}.json"
        write_json(
            growth_out_path,
            {
                "region": region,
                "as_of": as_of.strftime("%Y-%m-%d"),
                "universe": out.get("universe", "REAL"),
                "candidates": out.get("growth_candidates", []),
            },
        )
        print(f"✅ growth saved: {growth_out_path}")
        mkt = MarketDataClient()
        uni_tickers = [c["ticker"] for c in out.get("candidates", [])]
        if uni_tickers:
            prices, _ = mkt.get_prices(uni_tickers, lookback_days=260)
            region_prices[region] = prices

    # 価格を統合（列=ティッカー）
    import pandas as pd  # local import to avoid global dependency at import time
    all_prices = None
    for p in region_prices.values():
        if p is None or p.empty:
            continue
        all_prices = p if all_prices is None else all_prices.join(p, how="outer")

    portfolio = optimize_portfolio(
        candidates_by_region=candidates_all,
        constraints={
            "region_limits": cfg.region_limits,
            "position_limit": cfg.position_limit,
            "cash_min": cfg.cash_min,
            "cash_max": cfg.cash_max,
            "as_of": as_of.strftime("%Y-%m-%d"),
            "risk_aversion": risk_aversion,
            "target_vol": target_vol,
            "target": target,
        },
        prices_df=all_prices,
    )

    port_path = Path(cfg.output_dir) / f"portfolio_{as_of.strftime('%Y%m%d')}.json"
    write_json(port_path, portfolio)
    print(f"✅ portfolio saved: {port_path}")

    # リスク指標を計算・保存
    risk_agent = RiskAgent()
    risk = risk_agent.run(price_panels=region_prices, combined_prices=all_prices)
    risk_path = Path(cfg.output_dir) / f"risk_{as_of.strftime('%Y%m%d')}.json"
    write_json(risk_path, risk)

    # 図の保存（相関ヒートマップ、配分円グラフ）
    images = {}
    try:
        from .agents.chair import save_correlation_heatmap, save_allocation_pie
        corr_dict = (risk or {}).get("metrics", {}).get("correlation")
        corr_png = Path(cfg.output_dir) / f"corr_{as_of.strftime('%Y%m%d')}.png"
        save_correlation_heatmap(corr_dict, str(corr_png))
        images["correlation_heatmap"] = str(corr_png)
        pie_png = Path(cfg.output_dir) / f"alloc_{as_of.strftime('%Y%m%d')}.png"
        save_allocation_pie(portfolio, str(pie_png))
        images["allocation_pie"] = str(pie_png)
    except Exception:
        images = {}

    md = build_report(candidates_all=candidates_all, portfolio=portfolio, kpi=risk, macro=macro_weights, images=images)
    out_md = Path(cfg.output_dir) / f"report_{as_of.strftime('%Y%m%d')}.md"
    write_text(out_md, md)
    print(f"✅ report saved: {out_md}")


if __name__ == "__main__":
    app()


