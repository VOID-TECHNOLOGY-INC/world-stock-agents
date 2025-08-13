テストフォルダ全体の構成を把握するために一覧を取得します。続けて各テストファイルの中身を読み、観点ごとに監査します。
Ran tool
Ran tool

テスト監査のため、`tests/` 配下の全テストファイルと `conftest.py` を順に読み込みます。まずは主要ファイル5件から確認します。
Read file: /Volumes/SSD2TB_DATA/src/world-stock-agent/tests/conftest.py
Read file: /Volumes/SSD2TB_DATA/src/world-stock-agent/tests/unit/test_chair_report_macro.py
Read file: /Volumes/SSD2TB_DATA/src/world-stock-agent/tests/unit/test_chair_report.py
Read file: /Volumes/SSD2TB_DATA/src/world-stock-agent/tests/unit/test_macro_agent.py
Read file: /Volumes/SSD2TB_DATA/src/world-stock-agent/tests/unit/test_scoring.py

残りのユニットテストを一括で読み取り、網羅範囲とテスト観点を洗い出します。
Read file: /Volumes/SSD2TB_DATA/src/world-stock-agent/tests/unit/test_features_merge_fundamentals.py
Read file: /Volumes/SSD2TB_DATA/src/world-stock-agent/tests/unit/test_features_merge_fundamentals_growth.py
Read file: /Volumes/SSD2TB_DATA/src/world-stock-agent/tests/unit/test_features_merge_news.py
Read file: /Volumes/SSD2TB_DATA/src/world-stock-agent/tests/unit/test_news_yfinance_mapping.py
Read file: /Volumes/SSD2TB_DATA/src/world-stock-agent/tests/unit/test_scoring_growth_optional.py

残りのユニットテストもまとめて確認します。
Read file: /Volumes/SSD2TB_DATA/src/world-stock-agent/tests/unit/test_optimizer_invest_bounds.py
Read file: /Volumes/SSD2TB_DATA/src/world-stock-agent/tests/unit/test_optimizer_tool.py
Read file: /Volumes/SSD2TB_DATA/src/world-stock-agent/tests/unit/test_fundamentals_tool.py
Read file: /Volumes/SSD2TB_DATA/src/world-stock-agent/tests/unit/test_news_tool.py
Read file: /Volumes/SSD2TB_DATA/src/world-stock-agent/tests/unit/test_risk_tool.py

テスト網羅性を評価するため、主要な実装ファイルを読み取り、未テスト領域を洗い出します。続けて残りの関連ファイルも読みます。
Read file: /Volumes/SSD2TB_DATA/src/world-stock-agent/src/scoring/features.py
Read file: /Volumes/SSD2TB_DATA/src/world-stock-agent/src/scoring/normalize.py
Read file: /Volumes/SSD2TB_DATA/src/world-stock-agent/src/scoring/scoring.py
Read file: /Volumes/SSD2TB_DATA/src/world-stock-agent/src/tools/optimizer_tool.py
Read file: /Volumes/SSD2TB_DATA/src/world-stock-agent/src/tools/risk_tool.py

主要未テスト領域を洗い出すために、`src/agents/*` と `src/io/*`、ならびに一部ツールと設定系をまとめて読みます。
Read file: /Volumes/SSD2TB_DATA/src/world-stock-agent/src/agents/chair.py
Read file: /Volumes/SSD2TB_DATA/src/world-stock-agent/src/agents/macro.py
Read file: /Volumes/SSD2TB_DATA/src/world-stock-agent/src/agents/openai_agent.py
Read file: /Volumes/SSD2TB_DATA/src/world-stock-agent/src/agents/optimizer.py
Read file: /Volumes/SSD2TB_DATA/src/world-stock-agent/src/agents/regions.py

テスト未網羅の可能性がある `src/io/*`, `src/tools/*` の実装と、`src/app.py`, `src/config.py`, `src/agents/risk.py` を読み取り、監査の精度を上げます。
Read file: /Volumes/SSD2TB_DATA/src/world-stock-agent/src/io/loaders.py
Read file: /Volumes/SSD2TB_DATA/src/world-stock-agent/src/io/writers.py
Read file: /Volumes/SSD2TB_DATA/src/world-stock-agent/src/tools/fundamentals.py
Read file: /Volumes/SSD2TB_DATA/src/world-stock-agent/src/tools/news.py
Read file: /Volumes/SSD2TB_DATA/src/world-stock-agent/src/tools/marketdata.py

残りのアプリ・設定・未確認エージェントの主要ファイルを確認し、未テスト領域の洗い出しを仕上げます。
Read file: /Volumes/SSD2TB_DATA/src/world-stock-agent/src/app.py
Read file: /Volumes/SSD2TB_DATA/src/world-stock-agent/src/config.py
Read file: /Volumes/SSD2TB_DATA/src/world-stock-agent/src/agents/risk.py

直近で `tests/` と主要実装を読み込み、テストの網羅状況とギャップを洗い出しました。これから観点別に簡潔に監査結果を共有します。

### 総評
- 現状のテストは「特徴量マージ」「正規化」「ニュース取得マッピング」「リスク指標の基本」「最適化の境界」「マクロ比率」「議長レポートの基本出力」をしっかりカバー。
- 一方で「エージェント間の統合」「I/O」「CLI」「一部ツールの重要分岐」「画像保存機能」「OpenAI 経路」などに未カバーが残っています。

### モジュール別の網羅状況
- ■ スコアリング/特徴量
  - **`src/scoring/normalize.py`**: OK。定数列・NaN列の正規化を確認（`test_normalize_features_handles_constant_and_nan`）。
  - **`src/scoring/scoring.py`**: 部分。基本列と成長列の扱い・列欠損時挙動は確認済み（`test_score_candidates_basic`, `test_scoring_growth_optional`）。重み変更の影響検証は未。
  - **`src/scoring/features.py`**: 部分。`merge_fundamentals` と `merge_news_signal` は十分にテスト済み。一方、`build_features_from_prices`（モメンタム・出来高トレンド・NaN境界）は未。
- ■ ツール
  - **`src/tools/news.py`**: OK。yfinance 由来のキー差異と since フィルタをモックで検証（`test_news_yfinance_mapping.py`, `test_news_tool.py`）。Import 失敗時のフォールバックまでは未。
  - **`src/tools/fundamentals.py`**: 部分。計算ロジックはモックで良好（ROIC/FCF/CAGR/EPS/NetDebt/EBITDA）。生データ取得 `_fetch_raw_financials` はネット依存のため未（許容）。
  - **`src/tools/risk_tool.py`**: 部分。pct 方式・形状・MDD の符号は確認。デフォルトの log 方式は未。
  - **`src/tools/optimizer_tool.py`**: 部分。ポジション上限・合計比率・投資下限域は良好（`test_optimizer_tool.py`, `test_optimizer_invest_bounds.py`）。地域上限のペナルティ効果そのものの検証は未。
  - **`src/tools/marketdata.py`**: 未。MultiIndex/単一ティッカー切替、欠落ティッカー補完、期間フィルタの動作を未検証。
- ■ エージェント
  - **`src/agents/macro.py`**: OK。キー集合・総和1を確認。
  - **`src/agents/chair.py`**: 部分。マクロ出力と上位3の表示、ポートフォリオ節は確認（`test_chair_report.py`, `test_chair_report_macro.py`）。AI 経路（`use_ai=True` 時の `is_openai_configured`/`generate_report_markdown`）や、`save_correlation_heatmap`/`save_allocation_pie` は未。
  - **`src/agents/optimizer.py`**: 未。`optimize_portfolio` の候補選定・価格系列未提供時フォールバック・出力整形は未。
  - **`src/agents/regions.py`**: 未。実データ経路（マーケットデータ→特徴量→ファンダ/ニュース統合→正規化/スコア→上位抽出）、例外時のダミー生成フォールバック、OpenAI gating の分岐は未。
  - **`src/agents/risk.py`**: 未。複数パネルの結合・空入力時の空メトリクス返却は未。
- ■ I/O・設定・CLI
  - **`src/io/loaders.py` / `src/io/writers.py`**: 未。CSV ユニバースの形式検証、JSON/テキスト書き出し。
  - **`src/config.py`**: 未。デフォルト値・環境変数反映。
  - **`src/app.py`**: 未。Typer コマンド（`candidates`, `report`, `run`）の E2E（出力ファイル生成・副作用）未。

### 気になる点・フレーク要因
- **リポジトリに `._test_chair_report_macro.py` が存在**（macOSのメタファイル）。テスト発見の邪魔はしにくいが、誤検出・混乱の温床。`.gitignore` に `._*` と `.DS_Store` を追加推奨。
- **乱数依存**（例: `RegionAgent` の `evidence`、ダミー特徴量）。テストでは乱数に依存しない形にする、または `rng` をモック/シード固定。
- **`matplotlib` の存在に依存**する画像保存関数。環境により ImportError で無害に `return` する設計だが、テストでは skip 条件を明示した方が安定。
- **ネットワーク依存**の可能性は概ねモックで回避できている（Good）。

### 追加すべきテスト（優先度順）
- **統合/エージェント**
  - `RegionAgent.run`:
    - マーケットデータ取得失敗時にダミーへフォールバックすること。
    - ファンダ/ニュース統合の後に正規化/スコア→`top_n` 抽出されること。
    - OpenAI 未設定時のフォールバック（`is_openai_configured=False`）での出力安定性。
  - `Optimizer.optimize_portfolio`:
    - 地域配分上限 × `position_limit` からの上位抽出ロジック。
    - 価格未提供時の合成リターン利用、`cash_weight` の整合性。
  - `RiskAgent.run`:
    - 複数地域の価格パネルを `outer join` してメトリクス生成。
    - 全て空のとき `{"metrics": {}}` を返すこと。
- **ツール**
  - `marketdata.get_prices`: `yfinance.download` をモックし、MultiIndex/単一ティッカー/欠落ティッカー補完/期間フィルタの各分岐を検証。
  - `risk_tool.compute_returns`: デフォルト `log` 方式の検証。
  - `optimizer_tool`: 地域ペナルティが実際に働くシナリオ（上限を超える構成）での検証。
  - `news.NewsClient`: `yfinance` Import 失敗時に空配列返却のフォールバック。
- **スコアリング/特徴量**
  - `build_features_from_prices`: 1m/3m/6m/12m モメンタム、出来高トレンド（10/60MA 比）、系列長不足時の `NaN`。
  - `ScoreWeights`: `growth` 重みを >0 にすると `score_overall` が変動すること。
- **エージェント/レポート周辺**
  - `chair.build_report`: `use_ai=True` で `is_openai_configured=True` かつ `generate_report_markdown` をモック→AI経路が使われること。
  - `save_correlation_heatmap`/`save_allocation_pie`: `tmp_path` への保存（`matplotlib` が無ければ `pytest.importorskip("matplotlib")` で skip）。
- **I/O・設定・CLI**
  - `loaders.load_universe`: 既存 `data/universe/JP.csv` を使うか、一時 CSV を使いフォーマット検証。
  - `writers.write_json`/`write_text`: `tmp_path` でのファイル生成。
  - `config.load_config`: 環境変数の有無で値が反映されること。
  - `app.candidates`/`app.run`/`app.report`: Typer の `CliRunner` で `tmp_path` 出力、`RegionAgent.run`/`MarketDataClient.get_prices` をモックし、アーティファクト（`candidates_*`, `growth_*`, `portfolio_*`, `risk_*`, `report_*.md`）が生成されること。

### 改善提案（テスト設計）
- **パラメタライズ活用**: 境界値（例: `cash_bounds`、`position_limit`、`region_limits`）を複数パターンで検証。
- **モックの粒度統一**: `monkeypatch` による import 置換はテスト毎にスコープを閉じる（現状OK）。`yfinance`/`matplotlib`/OpenAI 経路は関数単位で差し替え。
- **乱数固定**: `numpy.random.default_rng(seed)` をテスト側で差し替え、非決定性を排除。
- **不要ファイルの整理**: `tests/unit/._test_chair_report_macro.py` の削除と `.gitignore` 更新。

### 実行について
- `.venv` を使ってテスト実行する場合の例:  
  ```bash
  source .venv/bin/activate && pytest -q
  ```
- 以降の新規実装も小さな単位でテスト先行にするのが良さそうです（TDDのご方針に合わせて）[[memory:6057519]]。

- 重要ポイント
  - **統合パス（`regions`/`optimizer`/`risk`/`app`）が未カバー**。ここを最優先で補うと、回帰の検知力が大幅に上がります。
  - **マーケットデータ取得（`marketdata`）の分岐が未検証**。外部 API 形状の差異をモックで押さえると安心です。
  - **レポート画像保存や OpenAI 経路は軽量テストで十分**。I/O 存在確認と分岐到達で実質カバー完了。

- 次にやると良いこと
  - `RegionAgent.run`/`Optimizer.optimize_portfolio`/`RiskAgent.run` の3本にユニットを追加。
  - `marketdata.get_prices` のモックテストを追加。
  - `app.run` の E2E（`CliRunner` + `tmp_path`）で最小回しを1本。

以上です。必要なら上記優先3本からテスト実装をこちらで一気に進めます。

- 主要テストのカバー状況とギャップを整理
- 最優先で補うべき統合パスと外部依存分岐を特定
- 乱数・外部依存・画像依存の安定化方針を提示