# 実装計画（World Stock Agent）

本計画は `doc/specification.md` と改善提案文書（`improvement-1.md`, `improvement-grock4_20250815.md`）、フィードバック（`feedback-1.md`, `feedback-2.md`）を踏まえ、MVPの完成度を高めた上でWeek2以降の拡張へ段階的に到達するための実装ロードマップを定義する。

---

## 0. 目標（ゴール）
- 週次で JP/US/EU/CN の候補抽出→最適化→レポート生成を10分以内に完走。
- すべての候補に簡潔な日本語の `thesis` と最大3点の `risks` を付与。
- ポートフォリオは地域上限・銘柄上限・現金比率の制約を満たし、平均分散（MV）最適化の制御ノブ（`risk_aversion`, `target_vol`, `target`）をCLIから指定可能。
- レポート（Markdown）に、採用/不採用理由・主要KPI・図表（配分円グラフ/相関ヒートマップ）を含める。

---

## 1. スコープと優先度
- P0（信頼性/安全性）：MV最適化の強化、バリデーション、失敗時フォールバック、ログ強化、テスト拡充。
- P1（機能充実）：`fundamentals`/`news` を features に統合、`RiskAgent` のメトリクスをレポートへ反映、`MacroAgent` の初期重み適用。
- P2（高度化）：CVaR/Black-Litterman/ターンオーバー制約、バックテストの簡易枠組み、CI/DevEx向上。

---

## 2. 変更概要（実装単位）

### 2.1 Optimizer（P0）
- `src/tools/optimizer_tool.py`
  - `MVConfig` に `risk_aversion: float`, `target_vol: float | None` を追加。
  - 目的関数: 既定は分散最小。`risk_aversion>0` なら `var - risk_aversion * ret`。`target==max_return` は `-ret`。
  - 制約: `sum(w)` の投資比率境界、銘柄上限、年率ボラ上限 `w'Σw <= target_vol^2` をSLSQPに実装。
  - 地域上限は現行どおりペナルティ方式（将来的に線形制約化検討）。
  - 失敗時フォールバック: 成功しなければ `x0` を返し、ログに `res.message` を出力。
  - バリデーション（`__post_init__`）: `risk_aversion >= 0`、`target_vol is None or >0`、`target in {min_vol,max_return}`。
- `src/agents/optimizer.py`
  - `constraints` から `risk_aversion`, `target_vol`, `target` を受け取り `MVConfig` に反映。
  - `prices_df` 無指定時は合成リターンを生成（seed固定）。
- `src/app.py`
  - `run` に `--risk-aversion` `--target-vol` `--target {min_vol,max_return}` を追加し `optimize_portfolio` に受け渡し。
- `src/config.py`
  - デフォルト値: `risk_aversion=0.0`、`target_vol=None` を保持。

### 2.2 Risk/Report（P1）
- `src/agents/risk.py`
  - `compute_returns` を利用し、相関・年率ボラ・最大DDのメトリクスを計算して `risk_*.json` を出力。
- `src/agents/chair.py`
  - レポートにリスク設定（`target/risk_aversion/target_vol`）とKPI表（地域ボラ/相関）を追記。
  - 画像生成（円グラフ/相関ヒートマップ）は `matplotlib` 非存在時は安全にskip。

### 2.3 Features/Data（P1）
- `src/tools/fundamentals.py`, `src/tools/news.py`
  - 既存実装を活用し、`merge_fundamentals`/`merge_news_signal` の欠損/外れ値ロバスト化。
- `src/scoring/features.py`
  - テクニカル（1/3/6/12Mモメンタム、出来高トレンド）定義の境界を明示。系列不足時は `NaN`。
  - `normalize_features` 前に分位クリップ（例: 1%/99%）。

### 2.4 Macro（P1）
- `src/agents/macro.py`
  - CSVまたは固定ヒューリスティクスから地域初期重みを生成（総和=1.0、負値clip）。

### 2.5 DevEx/CI（P2）
- pre-commit（ruff/black/mypy）と GitHub Actions（pytest, lint, build）。
- `.gitignore` に `._*` と `.DS_Store` を追加整理。

---

## 3. テスト計画（TDD）
- ユニット
  - Optimizer: 目的関数切替、`risk_aversion` 増加で期待リターン非減少、`target_vol` 制約の遵守、地域ペナルティ。
  - Risk: `compute_returns`（log/pct）とメトリクス形状、空入力時の挙動。
  - Features: モメンタム/出来高トレンド/NaN境界、分位クリップの影響。
  - Tools: `marketdata.get_prices` の分岐（MultiIndex/単一銘柄/欠損）をモックで検証。
- 統合
  - `RegionAgent.run` → `optimize_portfolio` → `build_report` の最小ルート。
  - `RiskAgent.run` の複数地域パネル結合（outer join）と空入力時の `{}`。
- CLI/E2E
  - `app.run` で `candidates_*`, `growth_*`, `portfolio_*`, `risk_*`, `report_*.md` が `artifacts/` に生成されること。

---

## 4. 成果物とI/O
- 生成物：
  - `artifacts/candidates_{REGION}_{YYYYMMDD}.json`
  - `artifacts/growth_{REGION}_{YYYYMMDD}.json`
  - `artifacts/risk_{YYYYMMDD}.json`
  - `artifacts/portfolio_{YYYYMMDD}.json`
  - `artifacts/report_{YYYYMMDD}.md`（将来 `pdf`）
- メタ情報（再現性/観測可能性）：
  - `as_of`, `regions`, `position_limit`, `region_limits`, `cash_bounds`, `risk_aversion`, `target_vol`, `target`, `git.commit/branch`, 価格データ期間。

---

## 5. リスクと緩和策
- 数値不安定: SLSQP 失敗時フォールバック、境界チェック（weights, 投資比率）。
- 外部依存: yfinance/OpenAI/Perplexity はテストでモックし、ネットワーク非依存に。
- 非決定性: 乱数seed固定、図生成は条件付きskip。

---

## 6. スケジュール案
- Week2（P0完了）: Optimizer拡張＋テスト、`app.run` オプション連携、レポートに設定反映。
- Week3（P1前半）: RiskAgent とメトリクス出力、レポートKPI、featuresロバスト化。
- Week4（P1後半）: Macro初期重み、fundamentals/newsの精度向上、統合テスト拡充。
- Week5+（P2）: 高度最適化（CVaR/BL/ターンオーバー）、バックテスト、CI/DevEx整備。

---

## 7. 運用メモ
- 実行例：
  - `. .venv/bin/activate && python -m src.app run --date 2025-08-30 --regions JP,US,EU,CN --risk-aversion 5.0 --target-vol 0.18 --target min_vol`
- セキュリティ：`.env` にAPIキー、CIはシークレット経由。出力に「投資助言ではない」の注意書き。
