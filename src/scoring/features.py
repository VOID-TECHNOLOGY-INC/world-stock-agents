from __future__ import annotations

from datetime import date
import numpy as np
import pandas as pd


def build_features_from_dummy(region: str, as_of: date, size: int = 120) -> pd.DataFrame:
    """MVP: ダミーの銘柄と特徴量を生成。

    出力列:
      ticker, name, fundamental_x, technical_x, quality_x, news_x
    """
    rng = np.random.default_rng(hash((region, as_of)) % (2**32))
    tickers = [f"{region}{i:03d}" for i in range(size)]
    names = [f"{region}-Company-{i:03d}" for i in range(size)]

    df = pd.DataFrame({
        "ticker": tickers,
        "name": names,
        "fundamental_roic": rng.normal(0.2, 0.05, size).clip(0, 1),
        "fundamental_fcf_margin": rng.normal(0.15, 0.05, size).clip(0, 1),
        "technical_mom_12m": rng.normal(0.5, 0.2, size).clip(0, 1),
        "technical_volume_trend": rng.normal(0.5, 0.2, size).clip(0, 1),
        "quality_dilution": rng.normal(0.6, 0.15, size).clip(0, 1),
        "news_signal": rng.normal(0.5, 0.2, size).clip(0, 1),
    })
    return df


def build_features_from_prices(
    region: str,
    universe_df: pd.DataFrame,
    prices: pd.DataFrame,
    volumes: pd.DataFrame,
) -> pd.DataFrame:
    """価格データからテクニカル特徴量を生成。その他は定数(0.5)のMVP。

    - technical_mom_{1,3,6,12}m: リターン
    - technical_volume_trend: 直近10日/60日出来高移動平均の比率
    """
    tickers = [t for t in universe_df["ticker"] if t in prices.columns]
    if not tickers:
        return pd.DataFrame(columns=[
            "ticker", "name", "fundamental_roic", "fundamental_fcf_margin",
            "technical_mom_12m", "technical_mom_6m", "technical_mom_3m", "technical_mom_1m",
            "technical_volume_trend", "quality_dilution", "news_signal",
        ])

    feats = []
    for t in tickers:
        s = prices[t].dropna()
        v = volumes[t].dropna() if t in volumes else None
        if s.empty:
            continue
        def mom(days: int) -> float:
            if len(s) <= days or s.iloc[-days] == 0:
                return np.nan
            return float(s.iloc[-1] / s.iloc[-days] - 1.0)

        m12 = mom(252)
        m6 = mom(126)
        m3 = mom(63)
        m1 = mom(21)

        vol_trend = np.nan
        if v is not None and not v.empty:
            ma10 = v.rolling(10).mean()
            ma60 = v.rolling(60).mean()
            if not ma10.dropna().empty and not ma60.dropna().empty and ma60.iloc[-1] not in (0, np.nan):
                vol_trend = float(ma10.iloc[-1] / ma60.iloc[-1])

        name = universe_df.loc[universe_df["ticker"] == t, "name"].values[0]
        feats.append({
            "ticker": t,
            "name": name,
            # MVP: ファンダ/質/ニュースは一定値
            "fundamental_roic": 0.5,
            "fundamental_fcf_margin": 0.5,
            "technical_mom_12m": m12,
            "technical_mom_6m": m6,
            "technical_mom_3m": m3,
            "technical_mom_1m": m1,
            "technical_volume_trend": vol_trend,
            "quality_dilution": 0.5,
            "news_signal": 0.5,
            # 生のテクニカル指標データ（LLM分析用）
            "_raw_technical": {
                "mom_12m": m12,
                "mom_6m": m6,
                "mom_3m": m3,
                "mom_1m": m1,
                "volume_trend": vol_trend,
            },
        })

    return pd.DataFrame(feats)


def merge_fundamentals(features_df: pd.DataFrame, fundamentals_df: pd.DataFrame) -> pd.DataFrame:
    df = features_df.merge(fundamentals_df, on="ticker", how="left")
    # マッピング: 外部列名→内部スコアに寄与する列（MVPはROIC/FCF）
    if "roic" in df.columns:
        df["fundamental_roic"] = df["roic"].astype(float, errors="ignore").fillna(df["fundamental_roic"])
    if "fcf_margin" in df.columns:
        df["fundamental_fcf_margin"] = (
            df["fcf_margin"].astype(float, errors="ignore").fillna(df["fundamental_fcf_margin"])
        )
    # 成長指標（正規化を適用）
    if "revenue_cagr" in df.columns:
        from .normalize import normalize_growth_rate
        df["growth_revenue_cagr"] = df["revenue_cagr"].astype(float, errors="ignore").apply(normalize_growth_rate)
    if "eps_growth" in df.columns:
        from .normalize import normalize_growth_rate
        df["growth_eps_growth"] = df["eps_growth"].astype(float, errors="ignore").apply(normalize_growth_rate)
    return df


def merge_news_signal(features_df: pd.DataFrame, news_items: list[dict]) -> pd.DataFrame:
    if not news_items:
        return features_df
    df = features_df.copy()
    # MVP拡張: タイトルから簡易感情スコアを算出し、利用可能ならそれを使用。
    # それ以外は従来の件数スケールにフォールバック。
    import pandas as pd
    news_df = pd.DataFrame(news_items)
    if "ticker" not in news_df.columns:
        return df

    def _title_sentiment(title: str) -> float:
        # 非依存・軽量な辞書ベース感情（英語中心）。[-1,1]
        if not isinstance(title, str) or not title:
            return 0.0
        t = title.lower()
        pos_words = {
            "beat", "beats", "beat estimates", "surge", "rally", "jump", "record",
            "raise", "raises", "upgrade", "upgraded", "outperform", "strong",
            "growth", "accelerate", "accelerates", "expand", "expands",
        }
        neg_words = {
            "miss", "misses", "miss estimates", "slump", "plunge", "drop", "falls", "fall",
            "cut", "cuts", "downgrade", "downgraded", "underperform", "weak", "lawsuit",
        }
        score = 0
        for w in pos_words:
            if w in t:
                score += 1
        for w in neg_words:
            if w in t:
                score -= 1
        if score == 0:
            return 0.0
        # クリップし [-1,1]
        if score > 0:
            return min(1.0, float(score) / 3.0)
        return max(-1.0, float(score) / 3.0)

    use_sentiment = False
    if "title" in news_df.columns:
        try:
            news_df["_sent"] = news_df["title"].map(_title_sentiment)
            if (news_df["_sent"].abs() > 1e-9).any():
                use_sentiment = True
        except Exception:
            use_sentiment = False

    if use_sentiment:
        sent = news_df.groupby("ticker")["_sent"].mean().rename("_news_sent").reset_index()
        df = df.merge(sent, on="ticker", how="left")
        # [-1,1] -> [0,1]
        df["news_signal"] = ((df["_news_sent"].fillna(0.0) + 1.0) / 2.0).clip(0.0, 1.0)
        df.drop(columns=[c for c in ["_news_sent"] if c in df.columns], inplace=True)
        return df

    # フォールバック: 件数で0..1スケール
    counts = news_df.groupby("ticker").size().rename("news_count").reset_index()
    df = df.merge(counts, on="ticker", how="left")
    maxc = df["news_count"].max()
    if pd.notna(maxc) and maxc > 0:
        df["news_signal"] = df["news_count"].fillna(0) / maxc
    df.drop(columns=[c for c in ["news_count"] if c in df.columns], inplace=True)
    return df


