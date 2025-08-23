from __future__ import annotations

from typing import Iterable, Callable, Dict

import pandas as pd


def _fetch_metrics_yfinance(ticker: str) -> Dict[str, float]:
    """Fetch valuation and growth metrics for *ticker* using yfinance.

    Returns a dictionary with keys ``pe``, ``pb``, ``revenue_growth``,
    ``eps_growth`` and ``peg_ratio``. Missing values are returned as
    ``None``.
    """
    import yfinance as yf

    t = yf.Ticker(ticker)
    info = t.info

    eps_growth = None
    try:
        fin = t.financials
        if "Diluted EPS" in fin.index and fin.shape[1] >= 2:
            eps_latest = fin.loc["Diluted EPS"].iloc[0]
            eps_prev = fin.loc["Diluted EPS"].iloc[1]
            if pd.notna(eps_latest) and pd.notna(eps_prev) and eps_prev:
                eps_growth = (eps_latest - eps_prev) / abs(eps_prev)
    except Exception:
        # If any of the calls above fail we simply leave eps_growth as None
        pass

    return {
        "pe": info.get("trailingPE"),
        "pb": info.get("priceToBook"),
        "revenue_growth": info.get("revenueGrowth"),
        "eps_growth": eps_growth,
        "peg_ratio": info.get("pegRatio"),
    }


def evaluate_buy_signals(
    tickers: Iterable[str],
    fetcher: Callable[[str], Dict[str, float]] | None = None,
    pe_threshold: float = 15.0,
    pb_threshold: float = 1.5,
    revenue_growth_threshold: float = 0.05,
    eps_growth_threshold: float = 0.10,
    peg_ratio_threshold: float = 1.0,
    min_signals: int = 3,
) -> pd.DataFrame:
    """Evaluate simple buy signals for a list of *tickers*.

    A ticker is marked as ``BUY`` when at least ``min_signals`` of the
    following conditions are met:

    - ``PE`` < ``pe_threshold``
    - ``PB`` < ``pb_threshold``
    - ``revenue_growth`` > ``revenue_growth_threshold``
    - ``eps_growth`` > ``eps_growth_threshold``
    - ``peg_ratio`` < ``peg_ratio_threshold``

    Parameters
    ----------
    tickers: Iterable[str]
        Tickers to evaluate.
    fetcher: Callable[[str], Dict[str, float]] | None
        Optional function returning a dict with keys ``pe``, ``pb``,
        ``revenue_growth``, ``eps_growth`` and ``peg_ratio``. Defaults to
        fetching via yfinance.
    pe_threshold: float
        Maximum P/E ratio considered attractive.
    pb_threshold: float
        Maximum P/B ratio considered attractive.
    revenue_growth_threshold: float
        Minimum revenue growth rate considered attractive.
    eps_growth_threshold: float
        Minimum EPS growth rate considered attractive.
    peg_ratio_threshold: float
        Maximum PEG ratio considered attractive.
    min_signals: int
        Minimum number of metrics that must meet their thresholds to mark
        a ticker as ``BUY``.

    Returns
    -------
    pandas.DataFrame
        Columns: ticker, pe, pb, revenue_growth, eps_growth, peg_ratio,
        score, decision.
    """
    fetcher = fetcher or _fetch_metrics_yfinance
    rows = []
    for t in tickers:
        metrics = fetcher(t) or {}
        pe = metrics.get("pe")
        pb = metrics.get("pb")
        rg = metrics.get("revenue_growth")
        epsg = metrics.get("eps_growth")
        peg = metrics.get("peg_ratio")

        score = 0
        if pe is not None and pe < pe_threshold:
            score += 1
        if pb is not None and pb < pb_threshold:
            score += 1
        if rg is not None and rg > revenue_growth_threshold:
            score += 1
        if epsg is not None and epsg > eps_growth_threshold:
            score += 1
        if peg is not None and peg < peg_ratio_threshold:
            score += 1

        decision = "BUY" if score >= min_signals else "HOLD"

        rows.append({
            "ticker": t,
            "pe": pe,
            "pb": pb,
            "revenue_growth": rg,
            "eps_growth": epsg,
            "peg_ratio": peg,
            "score": score,
            "decision": decision,
        })
    return pd.DataFrame(rows)
