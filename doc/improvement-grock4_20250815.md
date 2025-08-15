## 改善提案（grock4, 2025-08-15）

### 概要（ハイライト）
- **最適化の拡張**: ユーザー指定のリスク許容度（`risk_aversion`）と目標ボラ（`target_vol`）を導入し、`MVConfig` と CLI で制御可能に。
- **テスト網羅の強化**: 統合/E2E/CLI テストを追加し、非決定性の排除（乱数seed）と外部依存（yfinance/OpenAI/matplotlib）のモックを徹底。
- **データ統合の深化**: `fundamentals`/`news` を実運用に耐える形で `features` に取り込み。ニュースは軽量感情スコアを標準化して利用。
- **観測可能性・再現性**: 出力に実行設定（パラメータ、commit hash、データ期間）を記録。ログを構造化。
- **DevEx/CI**: pre-commit（ruff/black/mypy）、GitHub Actions によるテスト・lint・ビルド、`.gitignore` 強化。

---

### 優先度付きロードマップ
- P0（安全性・品質の底上げ）
  - `optimizer_tool` に `risk_aversion`/`target_vol` を追加し、`agents/optimizer.py` と `app.run` から渡す。
  - 失敗時フォールバックとバリデーション（非現実的 `target_vol`、負の `risk_aversion` など）。
  - 乱数seedの固定、ログの構造化（json/tsv）。
  - CLI/E2E 最小テスト（Typer `CliRunner`）。
- P1（機能充実）
  - `features.merge_fundamentals`/`merge_news_signal` の重みづけ改善と欠損ロバスト化（RobustScaler/分位クリップ）。
  - `RiskAgent` のメトリクスをレポートへ明示出力（相関/ボラ/最大DDを表と図で）。
  - `MacroAgent` のCSV駆動＋基本ヒューリスティクスを README に明文化。
- P2（高度化）
  - 最適化の選択肢追加（CVaR/Black-Litterman/回転抑制のターンオーバー制約）。
  - バックテスト簡易枠組み（週次TE/ボラ/DDを artifacts に時系列蓄積）。

---

### 最適化（optimizer）
- 目的関数・制約
  - `MVConfig` に以下を追加: `risk_aversion: float = 0.0`, `target_vol: float | None = None`。
  - 目的関数: 既定は `var`、`risk_aversion>0` で `var - risk_aversion * ret`、`target==max_return` は `-ret`。
  - ボラ上限: `w' Σ w <= target_vol^2` を SLSQP の不等式制約に追加。
  - 地域上限: 現状のペナルティ方式は維持しつつ、将来的に線形制約化も検討。
- 数値安定性
  - `if cfg.risk_aversion > 0 and mu is not None:` の明示化（falsy判定を避ける）。
  - 最適化失敗時は `x0` を返却しつつ、ログへ `res.message` を出力。
- パラメータバリデーション
  - `risk_aversion >= 0`、`target_vol is None or target_vol>0`、`target in {min_vol,max_return}` を `__post_init__` で検証。
- 出力の説明可能性
  - `portfolio_*.json` に `notes` とともに、`target/risk_aversion/target_vol` をレポートのサマリーへ反映。
- テスト（追加）
  - `risk_aversion` 増加で期待リターンが非減少。
  - `target_vol` 制約の遵守（不可達時でも安全に終了）。
  - 地域上限ペナルティが効くケースの確認。

---

### リスク（risk_tool / RiskAgent）
- `compute_returns` 方式の統一（`pct`/`log`）と選択肢の明記、`RiskAgent` の内部でメソッド指定を受け取れるよう拡張。
- `risk_metrics` の戻り値に `portfolio_level`（等加重や最終ウェイトでの推定ボラ/DD）を拡張可能に。
- 図出力の安定化（`matplotlib` が無ければ skip、tests は `importorskip`）。

---

### データ統合（marketdata/fundamentals/news → features）
- `fundamentals`
  - 欠損・ゼロ割りの安全化、`net_debt_to_ebitda` の分母0回避、単位系の明記。
  - 将来の安定API移行を見越したIF固定（現状yfinanceの制約をドキュメント化）。
- `news`
  - タイトル軽量感情は [-1,1] → [0,1] へ線形写像済み。語彙表の拡充と否定語処理を TODO から仕様化。
  - `since` フィルタの境界日付の扱いをテストで固定。
- `features`
  - テクニカル: 1/3/6/12ヶ月モメンタムの定義（営業日換算）と系列不足時の `NaN` 処理を明文化。
  - 正規化: `normalize_features` で外れ値にロバストな分位クリップ（例: 1%/99%）。

---

### エージェント（regions/macro/optimizer/chair）
- `RegionAgent`
  - 取得失敗時のダミー生成フォールバックをユニットテスト化。`evidence` の乱数依存をseed固定。
- `MacroAgent`
  - CSV重み取り込み時の検証（負値clip、対象地域での正規化）。
- `Chair`
  - `use_ai=True` 経路のモックテスト、`is_openai_configured()` の分岐を明示。
  - レポートにリスク設定と主要KPI表（地域ボラ/相関）を追記。

---

### CLI/アプリ（`src/app.py`）
- `run` に以下オプション（デフォルトは後方互換）:
  - `--risk-aversion`, `--target-vol`, `--target {min_vol,max_return}`
  - `--macro-csv`（既存）、`--verbose/-v`（進捗可視化）
- 生成アーティファクトの存在確認とパス出力（既存OK）。
- Typer 用 `CliRunner` で E2E 最小ケースを追加。

---

### テスト戦略（TDD）
- ユニット
  - `optimizer_tool`: 境界（position/cash/region/vol）と目的関数切替。
  - `features`: モメンタム/出来高トレンド/NaN境界。
  - `news`: yfinance差異（headline/link/providerPublishTime）をモックで吸収。
- 統合
  - `RegionAgent.run` → `optimize_portfolio` → `build_report` までの薄い統合。
  - `RiskAgent.run` の複数地域パネル結合（outer join）と空入力時挙動。
- CLI/E2E
  - `app.run` で `artifacts/` に `candidates_*`, `growth_*`, `portfolio_*`, `risk_*`, `report_*.md` が生成されること。
- 安定化
  - 乱数seed固定、ネットワークはモック、画像生成は `importorskip`。

---

### DevEx / CI / 品質
- pre-commit: `ruff`, `black`, `mypy` を導入。`requirements.txt` は上限ピンまたは `uv pip compile` を活用。
- GitHub Actions: `pytest -q`, lint, 依存キャッシュ、Artifacts 保存。
- `.gitignore`: `._*`, `.DS_Store`, `artifacts/*.png`, `artifacts/*.md`（必要に応じ）を整理。
- Makefile: 失敗時にエラー終了、`test`, `lint`, `format` ターゲット追加。

---

### 観測可能性・再現性
- すべての `portfolio_*.json` と `report_*.md` に以下メタを追記/記録：
  - `as_of`, `regions`, `position_limit`, `region_limits`, `cash_bounds`, `risk_aversion`, `target_vol`, `target`。
  - 実行 `git` の `commit`/`branch`、価格データの期間（最古/最新日付）。
- ログ: 構造化（tsv/json）、WARNING 以上で外部依存の失敗を記録（ティッカー・試行回数）。

---

### セキュリティ/法令・注意
- README とレポートに「投資助言ではない」明記（既存維持）。
- 外部APIの利用規約順守、PII 不扱いの確認、OpenAI キー漏えい防止（`.env` + CI secret）。

---

### 次のアクション（小さなPRに分割）
1) `optimizer_tool`/`agents/optimizer.py`/`app.run` に `risk_aversion`/`target_vol` を導入（単体・統合テスト含む）。
2) レポートにリスク設定サマリーとKPI表を追記（図は既存関数を活用）。
3) `features` テクニカル/ニュース/ファンダの境界テスト追加とロバスト化。
4) CLI/E2E 最小ケースを Typer で追加し、CI へ組込み。
5) pre-commit/ruff/black/mypy と `.gitignore` 更新、Makefile に `test/lint` 追加。


