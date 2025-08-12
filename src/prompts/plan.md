# 実装計画 (Week2 以降)

## 目的
- 仕様追補 (spec 18–20章) に基づき、MVPからWeek2へ機能拡張する。
- 実データ (価格/ファンダ/ニュース) を統合し、最適化とリスク制約を本実装する。

## スコープ
- 地域: JP / US / EU / CN
- 出力: 週次レポ (Markdown→将来PDF)、候補JSON、最終ポートフォリオJSON、リスク指標CSV/JSON

## タスク一覧と優先度

### P0: 最適化とリスクの本実装
1. tools/risk_tool.py
   - returns_df (日次リターン) から相関行列、年率ボラ、最大ドローダウン算出
   - I/O: risk_metrics(returns_df) -> dict
2. agents/risk.py
   - 候補セット単位でリスク集計し、地域・銘柄制約の事前チェック (違反フラグ) を付与
3. tools/optimizer_tool.py (平均分散)
   - 目的: 最小ボラ or 期待リターン最大 (切替)
   - 制約: 地域上限、銘柄上限、現金比率
   - 実装: scipy.optimize.minimize で重み最適化
4. agents/optimizer.py 改修
   - 現行の等配から、tools/optimizer_tool.py を呼ぶ構造に変更

### P0: データの多様化
1. tools/fundamentals.py
   - yfinance/yahooquery 等で ROIC / FCF/売上 / 売上CAGR / EPS成長 / NetDebt-EBITDA を取得
   - 欠損はNaNで保持し、正規化時にロバスト処理
2. tools/news.py
   - Yahoo Finance / RSS 等からタイトル / URL / 日付 / ティッカーを収集
   - 直近30/90日のポジ/ネガ件数を集計 → news_signal に反映
3. scoring/features.py 拡張
   - ファンダ・ニュース指標を取り込み、score_* を更新

### P1: マクロ・配分
1. agents/macro.py
   - 為替・金利・商品指数から地域初期重みを提案 (当面はCSV/定数ドライバ)
2. app.py のシーケンス
   - macro → risk → optimizer → chair を明示

### P1: レポート強化
1. agents/chair.py 拡張
   - 採否理由 (上位3指標 + 根拠リンク) / マクロ概況 / リスク表・図を出力
   - Matplotlib で相関ヒートマップ・配分円グラフを生成し、画像をMDに埋め込み
2. tools/report.py (将来)
   - md → pdf 変換の実装ポイント

### P2: 品質と運用
1. tests/ (unit / integration)
   - 特徴量、正規化、スコア、制約チェック、最適化の検証
2. ロギング/監査
   - logs/{YYYYMMDD}/... に外部取得の source, timestamp, request-id を保存
3. GitHub Actions
   - 週次ジョブ (cron) で make run-weekly を実行

## インタフェースとI/O
- mcp-fundamentals: get_fundamentals(tickers, fields) -> DataFrame
- mcp-news: get_news(tickers, since) -> list[NewsItem]
- mcp-risk: risk_metrics(returns_df) -> dict
- mcp-optimizer: optimize(candidates, constraints) -> weights

## 受け入れ基準 (DoD)
- 候補の80%以上で evidence(url/date or metric) を最低1件確保
- 平均分散の制約を全て満たす (自動テストで検証)
- リスク指標 (相関・年率ボラ・最大DD) を artifacts/ に保存
- make run-weekly が10分以内に完走し、report_*.md と portfolio_*.json が生成

## リスクと緩和
- 公開APIのレート制限: キャッシュ / 再試行 / 並列度制御
- 欠損・外れ値: 正規化前のロバスト補完、スコアのNaNセーフ
- 市場休日・時系列欠損: 左結合 + 前方埋め

## スケジュール (目安)
- Week2 前半: リスク・最適化、ニュースツール
- Week2 後半: ファンダツール、スコア統合、レポ強化
- Week3: マクロ、PDF、テスト・CI
