from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

import typer
import pandas as pd
from rich import print
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.layout import Layout

from .config import load_config
from .io.writers import ensure_output_dir, write_json, write_text
from .io.loaders import load_universe
from .agents.regions import RegionAgent
from .agents.chair import build_report
from .agents.optimizer import optimize_portfolio
from .tools.marketdata import MarketDataClient
from .tools.fundamentals import FundamentalsClient
from .tools.news import NewsClient
from .agents.risk import RiskAgent
from .agents.macro import MacroAgent
from .tools.risk_tool import compute_returns
from .tools.buy_signal import evaluate_buy_signals


app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()


def _parse_date(d: str) -> date:
    return datetime.strptime(d, "%Y-%m-%d").date()


def _create_progress_layout():
    """進捗表示用のレイアウトを作成"""
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main"),
        Layout(name="footer", size=3)
    )
    layout["main"].split_row(
        Layout(name="progress", ratio=2),
        Layout(name="status", ratio=1)
    )
    return layout


def _create_status_table():
    """ステータステーブルを作成"""
    table = Table(title="エージェントステータス")
    table.add_column("エージェント", style="cyan")
    table.add_column("ステータス", style="green")
    table.add_column("処理時間", style="yellow")
    return table


def _process_region_parallel(region: str, as_of: date, top_n: int, output_dir: Path, progress, task_id: int, workers: int = 4) -> tuple[str, dict, Any]:
    """地域別エージェントを並列実行する関数（スレッド安全な進捗更新）"""
    def _safe_update(**kwargs) -> None:
        try:
            # rich.Progress は call_from_thread を提供
            progress.call_from_thread(progress.update, task_id, **kwargs)
        except Exception:
            progress.update(task_id, **kwargs)
    try:
        # クライアントを共有（キャッシュ/接続の再利用）
        _safe_update(advance=20, description=f"[cyan]地域 {region} エージェント初期化中...")
        mkt = MarketDataClient(max_workers=workers)
        fcli = FundamentalsClient(max_workers=workers)
        ncli = NewsClient(max_workers=min(workers, 3))  # ニュースは控えめに
        agent = RegionAgent(name=region, universe="REAL", tools={
            "marketdata": mkt,
            "fundamentals": fcli,
            "news": ncli,
        })
        
        # 候補選定
        _safe_update(advance=30, description=f"[cyan]地域 {region} 候補選定中...")
        out = agent.run(as_of=as_of, top_n=top_n)
        
        # ファイル保存
        _safe_update(advance=20, description=f"[cyan]地域 {region} ファイル保存中...")
        out_path = output_dir / f"candidates_{region}_{as_of.strftime('%Y%m%d')}.json"
        write_json(out_path, out)
        
        # 成長候補を別ファイルに保存
        growth_out_path = output_dir / f"growth_{region}_{as_of.strftime('%Y%m%d')}.json"
        write_json(
            growth_out_path,
            {
                "region": region,
                "as_of": as_of.strftime("%Y-%m-%d"),
                "universe": out.get("universe", "REAL"),
                "candidates": out.get("growth_candidates", []),
            },
        )
        
        # 価格データ取得（同一クライアントを再利用）
        _safe_update(advance=20, description=f"[cyan]地域 {region} 価格データ取得中...")
        uni_tickers = [c["ticker"] for c in out.get("candidates", [])]
        region_prices = {}
        if uni_tickers:
            prices, _ = mkt.get_prices(uni_tickers, lookback_days=260)
            region_prices = prices
        
        _safe_update(advance=10, description=f"[green]地域 {region} 完了")
        
        return region, out, region_prices
        
    except Exception as e:
        try:
            progress.call_from_thread(progress.update, task_id, description=f"[red]地域 {region} エラー: {str(e)}")
        except Exception:
            progress.update(task_id, description=f"[red]地域 {region} エラー: {str(e)}")
        raise e


@app.command()
def candidates(
    regions: str = typer.Option("JP,US", help="対象地域 (CSV)"),
    run_date: str = typer.Option(datetime.today().strftime("%Y-%m-%d"), "--date"),
    output: str = typer.Option("./artifacts", help="出力先ディレクトリ"),
    top_n: int = typer.Option(50, help="各地域の上位候補数"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="詳細な進捗表示"),
    parallel: bool = typer.Option(True, "--parallel/--sequential", help="並列実行（デフォルト）または逐次実行"),
    workers: int = typer.Option(4, "--workers", "-w", help="並列ワーカー数（デフォルト: 4）"),
):
    """地域別エージェントを実行し、候補JSONを出力する。"""
    as_of = _parse_date(run_date)
    cfg = load_config(output)
    ensure_output_dir(cfg.output_dir)

    region_list = [r.strip().upper() for r in regions.split(",") if r.strip()]
    
    if verbose:
        console.print(Panel(
            f"[bold blue]地域別候補選定開始[/bold blue]\n"
            f"地域: {', '.join(region_list)}  日付: {as_of}\n"
            f"実行モード: {'並列' if parallel else '逐次'}",
            title="実行情報"
        ))
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            results: List[dict] = []
            
            if parallel and len(region_list) > 1:
                # 並列実行
                tasks = {}
                with ThreadPoolExecutor(max_workers=min(len(region_list), workers)) as executor:
                    # タスクを開始
                    for region in region_list:
                        task_id = progress.add_task(f"[cyan]地域 {region} 処理中...", total=100)
                        future = executor.submit(_process_region_parallel, region, as_of, top_n, Path(cfg.output_dir), progress, task_id)
                        tasks[future] = (region, task_id)
                    
                    # 完了を待機
                    for future in as_completed(tasks):
                        region, task_id = tasks[future]
                        try:
                            region_name, out, region_prices = future.result()
                            results.append(out)
                            console.print(f"✅ [green]candidates saved:[/green] candidates_{region}_{as_of.strftime('%Y%m%d')}.json")
                            console.print(f"✅ [green]growth saved:[/green] growth_{region}_{as_of.strftime('%Y%m%d')}.json")
                        except Exception as e:
                            console.print(f"❌ [red]地域 {region} でエラー:[/red] {str(e)}")
            else:
                # 逐次実行（既存の実装）
                for i, region in enumerate(region_list):
                    task = progress.add_task(f"[cyan]地域 {region} 処理中...", total=100)
                    
                    # エージェント実行
                    progress.update(task, advance=20, description=f"[cyan]地域 {region} エージェント初期化中...")
                    agent = RegionAgent(name=region, universe="REAL", tools={
                        "marketdata": MarketDataClient(max_workers=workers),
                        "fundamentals": FundamentalsClient(max_workers=workers),
                        "news": NewsClient(max_workers=min(workers, 3))
                    })
                    
                    progress.update(task, advance=30, description=f"[cyan]地域 {region} 候補選定中...")
                    out = agent.run(as_of=as_of, top_n=top_n)
                    results.append(out)
                    
                    progress.update(task, advance=30, description=f"[cyan]地域 {region} ファイル保存中...")
                    out_path = Path(cfg.output_dir) / f"candidates_{region}_{as_of.strftime('%Y%m%d')}.json"
                    write_json(out_path, out)
                    
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
                    
                    progress.update(task, advance=20, description=f"[green]地域 {region} 完了")
                    console.print(f"✅ [green]candidates saved:[/green] {out_path}")
                    console.print(f"✅ [green]growth saved:[/green] {growth_out_path}")
    else:
        print(f"[bold]Regions:[/bold] {region_list}  Date: {as_of}")
        
        results: List[dict] = []
        for region in region_list:
            agent = RegionAgent(name=region, universe="REAL", tools={
                "marketdata": MarketDataClient(max_workers=workers),
                "fundamentals": FundamentalsClient(max_workers=workers),
                "news": NewsClient(max_workers=min(workers, 3))
            })
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

    console.print(Panel("[bold green]候補選定完了[/bold green]", title="結果"))
    print("done.")


@app.command()
def report(
    input: str = typer.Option(..., help="最終ポートフォリオJSONのパス"),
    output: str = typer.Option("./artifacts", help="出力先ディレクトリ"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="詳細な進捗表示"),
):
    """最終ポートフォリオからMarkdownレポートを生成。"""
    cfg = load_config(output)
    ensure_output_dir(cfg.output_dir)

    if verbose:
        console.print(Panel("[bold blue]レポート生成開始[/bold blue]", title="実行情報"))
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            task = progress.add_task("[cyan]ポートフォリオ読み込み中...", total=100)
            progress.update(task, advance=30)
            
            with open(input, "r", encoding="utf-8") as f:
                portfolio = json.load(f)
            
            progress.update(task, advance=30, description="[cyan]レポート生成中...")
            md = build_report(candidates_all=[], portfolio=portfolio, kpi={})
            
            progress.update(task, advance=20, description="[cyan]ファイル保存中...")
            as_of = portfolio.get("as_of", datetime.today().strftime("%Y-%m-%d"))
            out_md = Path(cfg.output_dir) / f"report_{as_of.replace('-', '')}.md"
            write_text(out_md, md)
            
            progress.update(task, advance=20, description="[green]完了")
    else:
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
    target_vol: Optional[float] = typer.Option(None, help="年率ボラ上限（例: 0.18）。未指定で制約なし。"),
    target: str = typer.Option("min_vol", help="目的関数: min_vol / max_return（risk_aversion>0 ならトレードオフ）。"),
    macro_csv: Optional[str] = typer.Option(None, help="マクロ初期重みCSVのパス（region,weight）。未指定でデフォルト重み。"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="詳細な進捗表示"),
    parallel: bool = typer.Option(True, "--parallel/--sequential", help="並列実行（デフォルト）または逐次実行"),
    workers: int = typer.Option(4, "--workers", "-w", help="並列ワーカー数（デフォルト: 4）"),
):
    """週次エンドツーエンド実行。候補→最適化→レポ出力。"""
    as_of = _parse_date(run_date)
    cfg = load_config(output)
    ensure_output_dir(cfg.output_dir)

    region_list = [r.strip().upper() for r in regions.split(",") if r.strip()]
    
    if verbose:
        console.print(Panel(
            f"[bold blue]週次エンドツーエンド実行開始[/bold blue]\n"
            f"地域: {', '.join(region_list)}  日付: {as_of}\n"
            f"リスク許容度: {risk_aversion}  目的: {target}\n"
            f"実行モード: {'並列' if parallel else '逐次'}",
            title="実行情報"
        ))
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            # マクロエージェント
            task_macro = progress.add_task("[cyan]マクロ分析中...", total=100)
            progress.update(task_macro, advance=50)
            macro_agent = MacroAgent(csv_path=macro_csv)
            macro_weights = macro_agent.propose(region_list)
            progress.update(task_macro, advance=50, description="[green]マクロ分析完了")
            
            # 地域別エージェント（並列または逐次）
            candidates_all: List[dict] = []
            region_prices: dict[str, "pd.DataFrame"] = {}
            
            if parallel and len(region_list) > 1:
                # 並列実行
                tasks = {}
                with ThreadPoolExecutor(max_workers=min(len(region_list), workers)) as executor:
                    # タスクを開始
                    for region in region_list:
                        task_id = progress.add_task(f"[cyan]地域 {region} 処理中...", total=100)
                        future = executor.submit(_process_region_parallel, region, as_of, top_n, Path(cfg.output_dir), progress, task_id)
                        tasks[future] = (region, task_id)
                    
                    # 完了を待機
                    for future in as_completed(tasks):
                        region, task_id = tasks[future]
                        try:
                            region_name, out, prices = future.result()
                            candidates_all.append(out)
                            region_prices[region_name] = prices
                        except Exception as e:
                            console.print(f"❌ [red]地域 {region} でエラー:[/red] {str(e)}")
            else:
                # 逐次実行（既存の実装）
                for i, region in enumerate(region_list):
                    task_region = progress.add_task(f"[cyan]地域 {region} 処理中...", total=100)
                    
                    progress.update(task_region, advance=20, description=f"[cyan]地域 {region} エージェント初期化中...")
                    agent = RegionAgent(name=region, universe="REAL", tools={
                        "marketdata": MarketDataClient(max_workers=workers),
                        "fundamentals": FundamentalsClient(max_workers=workers),
                        "news": NewsClient(max_workers=min(workers, 3))
                    })
                    
                    progress.update(task_region, advance=30, description=f"[cyan]地域 {region} 候補選定中...")
                    out = agent.run(as_of=as_of, top_n=top_n)
                    candidates_all.append(out)
                    
                    progress.update(task_region, advance=20, description=f"[cyan]地域 {region} ファイル保存中...")
                    out_path = Path(cfg.output_dir) / f"candidates_{region}_{as_of.strftime('%Y%m%d')}.json"
                    write_json(out_path, out)
                    
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
                    
                    progress.update(task_region, advance=20, description=f"[cyan]地域 {region} 価格データ取得中...")
                    mkt = MarketDataClient(max_workers=workers)
                    uni_tickers = [c["ticker"] for c in out.get("candidates", [])]
                    if uni_tickers:
                        prices, _ = mkt.get_prices(uni_tickers, lookback_days=260)
                        region_prices[region] = prices
                    
                    progress.update(task_region, advance=10, description=f"[green]地域 {region} 完了")
            
            # 価格統合
            task_prices = progress.add_task("[cyan]価格データ統合中...", total=100)
            progress.update(task_prices, advance=50)
            import pandas as pd  # local import to avoid global dependency at import time
            all_prices = None
            for p in region_prices.values():
                if p is None or p.empty:
                    continue
                all_prices = p if all_prices is None else all_prices.join(p, how="outer")
            progress.update(task_prices, advance=50, description="[green]価格データ統合完了")
            
            # 最適化
            task_optimize = progress.add_task("[cyan]ポートフォリオ最適化中...", total=100)
            progress.update(task_optimize, advance=50)
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
            progress.update(task_optimize, advance=50, description="[green]最適化完了")
            
            # ポートフォリオ保存
            task_save = progress.add_task("[cyan]ポートフォリオ保存中...", total=100)
            progress.update(task_save, advance=50)
            port_path = Path(cfg.output_dir) / f"portfolio_{as_of.strftime('%Y%m%d')}.json"
            write_json(port_path, portfolio)
            progress.update(task_save, advance=50, description="[green]ポートフォリオ保存完了")
            
            # リスク計算
            task_risk = progress.add_task("[cyan]リスク指標計算中...", total=100)
            progress.update(task_risk, advance=50)
            risk_agent = RiskAgent()
            risk = risk_agent.run(price_panels=region_prices, combined_prices=all_prices)
            risk_path = Path(cfg.output_dir) / f"risk_{as_of.strftime('%Y%m%d')}.json"
            write_json(risk_path, risk)
            progress.update(task_risk, advance=50, description="[green]リスク計算完了")
            
            # 図の保存
            task_images = progress.add_task("[cyan]可視化画像生成中...", total=100)
            progress.update(task_images, advance=50)
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
            progress.update(task_images, advance=50, description="[green]可視化完了")
            
            # レポート生成
            task_report = progress.add_task("[cyan]レポート生成中...", total=100)
            progress.update(task_report, advance=50)
            md = build_report(candidates_all=candidates_all, portfolio=portfolio, kpi=risk, macro=macro_weights, images=images)
            out_md = Path(cfg.output_dir) / f"report_{as_of.strftime('%Y%m%d')}.md"
            write_text(out_md, md)
            progress.update(task_report, advance=50, description="[green]レポート生成完了")
        
        # 結果サマリー
        table = Table(title="生成ファイル")
        table.add_column("ファイル", style="cyan")
        table.add_column("ステータス", style="green")
        
        for region in region_list:
            table.add_row(f"candidates_{region}_{as_of.strftime('%Y%m%d')}.json", "✅ 完了")
            table.add_row(f"growth_{region}_{as_of.strftime('%Y%m%d')}.json", "✅ 完了")
        
        table.add_row(f"portfolio_{as_of.strftime('%Y%m%d')}.json", "✅ 完了")
        table.add_row(f"risk_{as_of.strftime('%Y%m%d')}.json", "✅ 完了")
        table.add_row(f"report_{as_of.strftime('%Y%m%d')}.md", "✅ 完了")
        if images:
            table.add_row(f"corr_{as_of.strftime('%Y%m%d')}.png", "✅ 完了")
            table.add_row(f"alloc_{as_of.strftime('%Y%m%d')}.png", "✅ 完了")
        
        console.print(table)
        console.print(Panel("[bold green]週次実行完了[/bold green]", title="結果"))
        
    else:
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


@app.command()
def buy_signal(
    regions: str = typer.Option("JP,US", help="対象地域 (CSV)"),
    run_date: str = typer.Option(datetime.today().strftime("%Y-%m-%d"), "--date"),
    output: str = typer.Option("./artifacts", help="出力先ディレクトリ"),
    pe_threshold: float = typer.Option(15.0, help="P/E比率の閾値"),
    pb_threshold: float = typer.Option(1.5, help="P/B比率の閾値"),
    revenue_growth_threshold: float = typer.Option(0.05, help="売上成長率の閾値"),
    eps_growth_threshold: float = typer.Option(0.10, help="EPS成長率の閾値"),
    peg_ratio_threshold: float = typer.Option(1.0, help="PEG比率の閾値"),
    min_signals: int = typer.Option(3, help="BUY判定に必要な条件数"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="詳細な進捗表示"),
):
    """買いシグナルを評価してCSVファイルに出力"""
    cfg = load_config(output)
    ensure_output_dir(cfg.output_dir)
    
    as_of = _parse_date(run_date)
    region_list = [r.strip() for r in regions.split(",")]
    
    if verbose:
        console.print(f"[bold]Buy Signal Analysis[/bold] regions={region_list} date={as_of}")
    
    all_tickers = []
    for region in region_list:
        try:
            uni = load_universe(region)
            all_tickers.extend(uni["ticker"].tolist())
        except Exception as e:
            console.print(f"❌ [red]地域 {region} のユニバース読み込みエラー:[/red] {str(e)}")
    
    if not all_tickers:
        console.print("[red]処理対象のティッカーが見つかりません[/red]")
        return
    
    if verbose:
        console.print(f"📊 [cyan]評価対象: {len(all_tickers)} ティッカー[/cyan]")
    
    # buy_signal評価実行
    result_df = evaluate_buy_signals(
        tickers=all_tickers,
        pe_threshold=pe_threshold,
        pb_threshold=pb_threshold,
        revenue_growth_threshold=revenue_growth_threshold,
        eps_growth_threshold=eps_growth_threshold,
        peg_ratio_threshold=peg_ratio_threshold,
        min_signals=min_signals,
    )
    
    # 結果をCSVに保存
    output_path = Path(cfg.output_dir) / f"buy_signals_{as_of.strftime('%Y%m%d')}.csv"
    result_df.to_csv(output_path, index=False)
    
    # BUY判定された銘柄を表示
    buy_candidates = result_df[result_df["decision"] == "BUY"]
    
    if verbose:
        console.print(f"✅ [green]buy_signals saved:[/green] {output_path}")
        console.print(f"📈 [green]BUY判定: {len(buy_candidates)} 銘柄[/green]")
        
        if not buy_candidates.empty:
            table = Table(title="BUY判定銘柄")
            table.add_column("ティッカー", style="cyan")
            table.add_column("P/E", style="yellow")
            table.add_column("P/B", style="yellow")
            table.add_column("売上成長", style="green")
            table.add_column("EPS成長", style="green")
            table.add_column("PEG", style="yellow")
            table.add_column("スコア", style="bold")
            
            for _, row in buy_candidates.head(20).iterrows():
                table.add_row(
                    row["ticker"],
                    f"{row['pe']:.2f}" if pd.notna(row['pe']) else "N/A",
                    f"{row['pb']:.2f}" if pd.notna(row['pb']) else "N/A",
                    f"{row['revenue_growth']:.1%}" if pd.notna(row['revenue_growth']) else "N/A",
                    f"{row['eps_growth']:.1%}" if pd.notna(row['eps_growth']) else "N/A",
                    f"{row['peg_ratio']:.2f}" if pd.notna(row['peg_ratio']) else "N/A",
                    str(row['score'])
                )
            console.print(table)
    
    console.print(Panel(f"[bold green]買いシグナル分析完了[/bold green]\nBUY判定: {len(buy_candidates)} 銘柄", title="結果"))


if __name__ == "__main__":
    app()


