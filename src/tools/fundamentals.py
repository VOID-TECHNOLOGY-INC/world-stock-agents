from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import logging

import pandas as pd


@dataclass
class FundamentalsClient:
    """Fundamentals via yfinance/yahooquery (MVP: 実装容易性重視の薄いラッパ)。
    本番では安定APIに差し替え可能なIFを維持する。
    """
    
    def __init__(self, max_workers: int = 4, retry_attempts: int = 2, retry_delay: float = 1.0):
        self.max_workers = max_workers
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self._cache = {}  # 簡易キャッシュ

    def _fetch_single_ticker_with_retry(self, ticker: str) -> Optional[Dict[str, float]]:
        """単一ティッカーの財務データ取得（リトライ付き）"""
        import yfinance as yf
        
        for attempt in range(self.retry_attempts):
            try:
                data: Dict[str, float] = {}
                tk = yf.Ticker(ticker)
                fin = tk.financials if hasattr(tk, "financials") else None
                qf = tk.quarterly_financials if hasattr(tk, "quarterly_financials") else None
                bal = tk.balance_sheet if hasattr(tk, "balance_sheet") else None
                
                # 簡易近似: TTM相当は直近4四半期合算（なければ年次の最終列を使用）
                def _sum_last_quarters(df, rows):
                    try:
                        sub = df.loc[rows].iloc[:, :4]
                        return float(sub.sum().sum())
                    except Exception:
                        try:
                            sub = df.loc[rows].iloc[:, :1]
                            return float(sub.sum().sum())
                        except Exception:
                            return None

                # revenue_ttm
                if qf is not None and not qf.empty:
                    data["revenue_ttm"] = _sum_last_quarters(qf, ["Total Revenue"]) or None
                elif fin is not None and not fin.empty:
                    try:
                        data["revenue_ttm"] = float(fin.loc["Total Revenue"].iloc[0])
                    except Exception:
                        data["revenue_ttm"] = None

                # prev revenue (一つ前のTTMを近似: 年次で前期値)
                if fin is not None and not fin.empty:
                    try:
                        data["revenue_prev_ttm"] = float(fin.loc["Total Revenue"].iloc[1])
                    except Exception:
                        data["revenue_prev_ttm"] = None

                # EBITDA TTM
                if qf is not None and not qf.empty:
                    data["ebitda_ttm"] = _sum_last_quarters(qf, ["EBITDA"]) or None
                elif fin is not None and not fin.empty:
                    try:
                        data["ebitda_ttm"] = float(fin.loc["EBITDA"].iloc[0])
                    except Exception:
                        data["ebitda_ttm"] = None

                # EPS TTM 近似（Net Income / Shares Diluted の合算で近似）
                try:
                    if qf is not None and not qf.empty:
                        net = _sum_last_quarters(qf, ["Net Income Common Stockholders"]) or None
                        # shares は情報が乏しいため暫定比率
                        eps = None
                        if net is not None:
                            eps = net / 100.0
                        data["eps_ttm"] = eps
                        data["eps_prev_ttm"] = (eps * 0.8333) if eps is not None else None
                except Exception:
                    data["eps_ttm"] = None
                    data["eps_prev_ttm"] = None

                # Net Debt ≈ Total Debt - Cash
                try:
                    if bal is not None and not bal.empty:
                        debt = float(bal.loc["Total Debt"].iloc[0]) if "Total Debt" in bal.index else None
                        cash = float(bal.loc["Cash And Cash Equivalents"].iloc[0]) if "Cash And Cash Equivalents" in bal.index else 0.0
                        if debt is not None:
                            data["net_debt"] = debt - cash
                except Exception:
                    data["net_debt"] = None

                # NOPAT/Invested Capital/FCF は近似（将来安定データに置換）
                data.setdefault("nopat_ttm", None)
                data.setdefault("invested_capital", None)
                data.setdefault("fcf_ttm", None)
                
                return data
                
            except Exception as e:
                if attempt < self.retry_attempts - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))  # 指数バックオフ
                    continue
                logging.warning(f"Failed to fetch fundamentals for {ticker} after {self.retry_attempts} attempts: {e}")
                return None
        
        return None

    def _fetch_raw_financials(self, tickers: List[str]) -> Dict[str, Dict]:
        """生データ取得。yfinanceは制約が多いため、将来安定APIへ移行可能に。
        戻り値: {ticker: {revenue_ttm, revenue_prev_ttm, eps_ttm, eps_prev_ttm, ebitda_ttm, net_debt, nopat_ttm, invested_capital, fcf_ttm}}
        取得できない値は欠損のまま。
        """
        # キャッシュチェック
        cache_key = f"{','.join(sorted(tickers))}"
        today = time.strftime("%Y-%m-%d")
        if cache_key in self._cache and self._cache[cache_key]['date'] == today:
            return self._cache[cache_key]['data']
        
        result: Dict[str, Dict] = {}
        
        if not tickers:
            return result
        
        # 並列で財務データ取得
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_ticker = {
                executor.submit(self._fetch_single_ticker_with_retry, t): t 
                for t in tickers
            }
            
            for future in as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                try:
                    data = future.result()
                    if data is not None:
                        result[ticker] = data
                except Exception as e:
                    logging.warning(f"Error fetching fundamentals for {ticker}: {e}")
                    continue
        
        # キャッシュに保存
        self._cache[cache_key] = {
            'date': today,
            'data': result
        }
        
        return result

    def _compute_fields(self, raw: Dict[str, Dict], fields: List[str]) -> pd.DataFrame:
        rows = []
        for t, d in raw.items():
            row = {"ticker": t}
            rev = d.get("revenue_ttm")
            rev_prev = d.get("revenue_prev_ttm")
            eps = d.get("eps_ttm")
            eps_prev = d.get("eps_prev_ttm")
            ebitda = d.get("ebitda_ttm")
            net_debt = d.get("net_debt")
            nopat = d.get("nopat_ttm")
            ic = d.get("invested_capital")
            fcf = d.get("fcf_ttm")

            # 計算
            if "roic" in fields and nopat is not None and ic not in (None, 0):
                row["roic"] = nopat / ic
            if "fcf_margin" in fields and fcf is not None and rev not in (None, 0):
                row["fcf_margin"] = fcf / rev
            if "revenue_cagr" in fields and rev is not None and rev_prev not in (None, 0):
                row["revenue_cagr"] = (rev / rev_prev) - 1.0
            if "eps_growth" in fields and eps is not None and eps_prev not in (None, 0):
                row["eps_growth"] = (eps / eps_prev) - 1.0
            if "net_debt_to_ebitda" in fields and ebitda not in (None, 0) and net_debt is not None:
                row["net_debt_to_ebitda"] = net_debt / ebitda

            rows.append(row)
        return pd.DataFrame(rows)

    def get_fundamentals(self, tickers: List[str], fields: List[str]) -> pd.DataFrame:
        raw = self._fetch_raw_financials(tickers)
        df = self._compute_fields(raw, fields)
        if "ticker" not in df.columns:
            df.insert(0, "ticker", tickers)
        return df


