先に要点：

* 地域別（JP/CN/US/EU）エージェント＋横断（マクロ/リスク/最適化/議長）で“合議制”にする
* データ取得はMCPで「marketdata / fundamentals / news / fx-commod / risk / optimizer / paper-broker / report」をモジュール化
* 出力は「週次レポ（Markdown/PDF）＋機械可読JSON（候補と配分）」を必ず同時に生成
* MVPはまずJP/USのみ＋CSV擬似データで動作→2週目にEU/CN・最適化追加

---

# 仕様書（Python × OpenAI Agents SDK）

## 0. ゴール

* 各地域の株式市場をエージェントが調査し、スコアリング → 横断評価 → リスク制約下で配分案を生成
* 週次で「採用銘柄・理由・配分・想定リスク」を**根拠リンク付き**で出力（レポ＋JSON）
* 初期はペーパー取引のみ（実売買なし）

---

## 1. 全体アーキテクチャ

* フレームワーク：OpenAI Agents SDK（エージェント間連携／Agents-as-Tools）
* ツール接続：MCP（各データ源やアルゴリズムを“標準ポート”化）
* 出力：

  * `/artifacts/report_{YYYYMMDD}.md` → PDF化
  * `/artifacts/portfolio_{YYYYMMDD}.json`（採用銘柄・配分）
  * `/artifacts/candidates_{REGION}_{YYYYMMDD}.json`（地域候補の素データ）
* 実行トリガ：CLI／cron／GitHub Actions（週次）

---

## 2. エージェント役割と責務

### 2.1 地域別エージェント（4つ）

* `JPAgent`, `CNAgent`, `USAgent`, `EUAgent`
* 入力：ユニバース定義（例：TOPIX500 / CSI300+HK / S\&P500+Nas100 / STOXX600）
* 仕事：

  1. スクリーニング（流動性/時価総額/除外銘柄）
  2. スコアリング（ファンダ・テクニカル・質・ニュース）
  3. 候補上位N（既定=50）のJSONと根拠（URL/日付/指標）を返す

### 2.2 マクロ統合エージェント

* 金利/為替/商品感応度から**地域配分の初期重み**を提案
* 例：US 45%, JP 25%, EU 20%, CN 10%

### 2.3 リスク管理エージェント

* 候補群の相関・ボラ・ドローダウンを計測
* ルール：銘柄上限7%、地域上限（例：US≤50%, JP≤30%, EU≤30%, CN≤20%）、推奨分散度

### 2.4 ポートフォリオ最適化エージェント

* 目的：ボラ最小 or 期待リターン最大（リスク上限・配分上限制約あり）
* 実装：平均分散/CVaR/Black-Littermanのいずれか切替可能（MVPは平均分散）

### 2.5 エクスプレイナ（議長）

* 全出力を取りまとめ、**採否理由**・**想定シナリオ**を言語化してレポ化
* 付随：ペーパー取引差分（増減/新規/解約）を出力

---

## 3. MCPツール仕様

| ツールID              | 概要            | 主なメソッド（入出力）                                             |
| ------------------ | ------------- | ------------------------------------------------------- |
| `mcp-marketdata`   | 価格・出来高・時価総額など | `get_prices(tickers, lookback_days) -> DataFrame`       |
| `mcp-fundamentals` | 財務・コンセンサス     | `get_fundamentals(tickers, fields) -> DataFrame`        |
| `mcp-news`         | ニュース/決算       | `get_news(tickers, since) -> list[NewsItem]`            |
| `mcp-fx-commod`    | 為替・コモディティ     | `get_macro_series(symbols, lookback_days) -> DataFrame` |
| `mcp-risk`         | 相関・ボラ・DD      | `risk_metrics(returns_df) -> dict`                      |
| `mcp-optimizer`    | 制約付き最適化       | `optimize(candidates, constraints) -> weights`          |
| `mcp-broker-paper` | ペーパー取引記録      | `propose_trades(prev_port, new_port) -> list[Trade]`    |
| `mcp-report`       | MD→PDF生成      | `render_markdown(md, out_pdf_path) -> None`             |

※ 初期は `mcp-marketdata` 等を**CSVバックエンド**で実装可（API置換可能な抽象化）。

---

## 4. スコアリング仕様

### 4.1 指標（MVP）

* ファンダ（上ほど重み高）

  * ROIC、FCF/売上、売上CAGR、EPS成長、ネット負債/EBITDA（低いほど◎）
* テクニカル

  * 1/3/6/12Mモメンタム（標準化合成）、出来高トレンド、決算後ギャップ持続
* 質（Quality）

  * 株主希薄化トレンド、インサイダー/機関の保有変化（取得可能なら）
* ニュース

  * 直近30/90日での好悪サイン（決算ビート/ガイダンス上方修正/M\&A等）

### 4.2 正規化と合成

* 各指標を0..1にMin-Max or RobustScalerで正規化
* 重み例：`fundamental 0.4, technical 0.35, quality 0.15, news 0.10`
* 最終 `score_overall = Σ w_i * score_i`
* 各候補に `thesis`（短い投資仮説）と `risks`（3点）を付与

---

## 5. データモデル（JSONスキーマ）

### 5.1 地域候補（出力）

```json
{
  "region": "US",
  "as_of": "2025-08-12",
  "universe": "SP500+Nasdaq100",
  "candidates": [
    {
      "ticker": "AAPL",
      "name": "Apple Inc.",
      "score_overall": 0.81,
      "score_breakdown": {
        "fundamental": 0.76,
        "technical": 0.86,
        "quality": 0.70,
        "news": 0.64
      },
      "thesis": "サービス比率上昇と粗利率の安定。",
      "risks": ["需要鈍化", "規制"],
      "evidence": [
        {"type": "news", "title": "Q3 earnings...", "url": "...", "date": "2025-08-08"},
        {"type": "metric", "name": "ROIC_TTM", "value": 32.1}
      ]
    }
  ]
}
```

### 5.2 最終ポートフォリオ

```json
{
  "as_of": "2025-08-12",
  "region_limits": {"US": 0.5, "JP": 0.3, "EU": 0.3, "CN": 0.2},
  "position_limit": 0.07,
  "weights": [
    {"ticker": "AAPL", "region": "US", "weight": 0.05},
    {"ticker": "MSFT", "region": "US", "weight": 0.05}
  ],
  "cash_weight": 0.0,
  "notes": "Mean-variance optimization, target_vol=12%"
}
```

---

## 6. ワークフロー（週次ジョブ）

1. 除外リスト更新（制裁/規制/低流動性）
2. 地域別エージェント実行 → `candidates_{REGION}.json` 保存
3. マクロ統合：地域初期重み提案
4. リスク管理：相関・ボラ・DD算出、違反候補へフラグ
5. 最適化：制約（地域/銘柄上限、キャッシュ）を満たす配分計算
6. エクスプレイナ：

   * 採用/不採用の**理由**（上位3指標＋根拠リンク）
   * 代替案（入替候補）
   * 想定シナリオ（Upside/Downside）
7. レポ生成（Markdown→PDF）、ペーパー取引ログ出力
8. 成果KPI更新（ボラ/TE/勝率等、CSV追記）

---

## 7. 開発構成

### 7.1 依存関係（例）

```
python>=3.11
pandas
numpy
scipy
pydantic
typer              # CLI
rich               # CLI出力
matplotlib         # 図表（レポ用）
openai             # APIクライアント
openai-agents      # Agents SDK（仮：実名は環境に合わせて）
mcp-toolkit        # MCPクライアント（仮）
```

### 7.2 環境変数

```
OPENAI_API_KEY=...
AGENTS_BASE_URL=...          # 必要に応じて
MCP_MARKETDATA_URL=wss://...
MCP_FUNDAMENTALS_URL=wss://...
...（各ツールURL）
```

### 7.3 ディレクトリ

```
repo/
  src/
    app.py                  # 週次実行エントリ
    config.py
    agents/
      regions.py            # JP/CN/US/EU 定義
      macro.py
      risk.py
      optimizer.py
      chair.py
    tools/                  # MCPツールラッパ
      marketdata.py
      fundamentals.py
      news.py
      fx_commod.py
      risk_tool.py
      optimizer_tool.py
      broker_paper.py
      report.py
    scoring/
      features.py           # 指標算出
      normalize.py
      scoring.py            # 合成ロジック
    io/
      loaders.py            # CSV/パーサ
      writers.py            # JSON/MD/PDF
    prompts/
      region_agent.md
      chair_agent.md
  data/                     # CSVダミー or 取得キャッシュ
  artifacts/                # 出力
  tests/
    unit/
    integration/
  requirements.txt
  README.md
```

---

## 8. 主要クラス/関数IF（擬似）

```python
# src/tools/marketdata.py
class MarketDataClient:
    def get_prices(self, tickers: list[str], lookback_days: int) -> "pd.DataFrame": ...

# src/scoring/scoring.py
@dataclass
class ScoreWeights:
    fundamental: float = 0.4
    technical: float = 0.35
    quality: float = 0.15
    news: float = 0.10

def score_candidates(df_features: "pd.DataFrame", weights: ScoreWeights) -> "pd.DataFrame": ...

# src/agents/regions.py
class RegionAgent:
    def __init__(self, name: str, universe: str, tools: dict): ...
    def run(self, as_of: date) -> dict: ...  # returns candidates JSON

# src/agents/optimizer.py
def optimize_portfolio(candidates_by_region: list[dict], constraints: dict) -> dict: ...

# src/agents/chair.py
def build_report(candidates_all: list[dict], portfolio: dict, kpi: dict) -> str: ...
```

---

## 9. プロンプト設計（要旨）

### 地域エージェント（`prompts/region_agent.md`）

* 指示：

  * 「与えられたユニバースから流動性＆除外ルールでフィルタ」
  * 「定義済み特徴量でスコアリング、上位N=50をJSON返却」
  * 「各候補に thesis（1～2文）と risks（最大3）を付け、**根拠URLと日付**を添付」
  * 「未確認情報の推測は禁止。出典がない指標は空欄に」

### 議長（`prompts/chair_agent.md`）

* 指示：

  * 「全地域候補と最適化結果から採用/不採用の**理由**を簡潔に」
  * 「上位3指標と根拠リンクを明示。Downside想定も必ず」
  * 「Markdownの見出し・表・箇条書きを使用」

---

## 10. レポート構成（Markdown）

1. サマリー（今週の採用/入替、地域配分、想定ボラ）
2. 地域別ハイライト（上位3銘柄、理由、リスク、根拠）
3. マクロ概況（為替・金利・商品）
4. リスク指標（相関マトリクス、想定ドローダウン）
5. 最終ポートフォリオ（表・円グラフ）
6. 取引案（新規/増減/解約）
7. 付録（全候補JSONの要約）

---

## 11. ルール＆制約

* 地域上限：`US≤0.5, JP≤0.3, EU≤0.3, CN≤0.2`
* 銘柄上限：`≤0.07`
* 最小ウェイト：`≥0.01`（ノイズ抑制、MVPでは任意）
* 現金比率：`0~10%`（不確実時に許容）

---

## 12. ロギング/監査

* すべての外部取得に **source, timestamp, request-id** を付与して保存
* エージェント入出力は `/logs/{YYYYMMDD}/...` にJSONで説明可能性を確保
* 乱数・最適化のseed固定

---

## 13. テスト計画

* ユニット：特徴量計算、正規化、合成スコア、制約チェック
* 統合：CSVダミーでJP/USの end-to-end（候補→最終配分→レポ）
* 回帰：1週間分の固定データで**同一出力**を検証
* バックテスト（任意）：過去データで週次リバランスの指標を算出（ボラ、TE、DD）

---

## 14. セキュリティ/法令・注意

* これは**投資助言ではない**デモとして提供（ドキュメントに明示）
* データ利用規約の順守（スクレイピング不可、API or CSV受領）
* 個人情報なし、ティッカー等の公開情報のみ扱う
* 出力に必ず「参考値・最終判断は利用者」の但し書き

---

## 15. MVPスコープ

* Week1：JP/USのみ、CSVデータで `score_overall` 作成 → JSON/MD出力
* Week2：EU/CN追加、為替/マクロ反映、最適化＆リスク制約導入、PDF化

---

## 16. 受け入れ基準（Definition of Done）

* `make run-weekly` で **10分以内**に end-to-end 完走
* `artifacts/` に `report_*.pdf` と `portfolio_*.json` が生成
* 各採用銘柄に**最低1つ以上の根拠URLと日付**
* ルール（地域/銘柄上限）を1件も違反しない
* ログに全データ取得の`source/timestamp`記録がある

---

## 17. CLI設計（Typer例）

```
# 週次実行
python -m src.app run --date 2025-08-12 --regions JP,US,EU,CN --output ./artifacts

# 候補のみ生成
python -m src.app candidates --regions JP,US

# レポのみ再生成
python -m src.app report --input ./artifacts/portfolio_20250812.json
```

---

ここまでを“そのまま実装に落とせる粒度”にしています。
必要なら **CSVダミーデータと最小コード骨格** も続けて用意します。どの部分から着手しますか？（例：特徴量→スコア→JSON出力 or MCPツールのモック作成）

---

## 18. 監査フィードバック反映（2025-08-12）

現状（MVP/Week1）の実装状況とギャップを踏まえ、以下の通り仕様を補強する。

- 実装済（要点）
  - `RegionAgent` によるユニバース読み込み、実価格データ（yfinance）からのテクニカル特徴量→正規化→スコア→候補JSONの出力（JP/US/EU/CN対応）
  - `optimize_portfolio` による制約下の均等配分（地域上限/銘柄上限の尊重）
  - `Chair` によるMarkdownレポ生成（OpenAIがあればLLM生成、無ければテンプレ）

- 主なギャップ（未実装）
  1. `MacroAgent` と `RiskAgent` が未実装（マクロ起点の地域初期重み、相関・ボラ・DDの評価）
  2. MCPツールの不足：`fundamentals`, `news`, `risk`, `optimizer`（現状は `marketdata` のみ実装）
  3. 最適化アルゴリズム：平均分散/CVaR/Black-Litterman等の本格実装が未着手（均等配分のみ）
  4. レポートの説明力：採否理由・根拠リンク・シナリオの体系化が限定的（フォールバック時）

---

## 19. 追加仕様（Week2・拡張）

### 19.1 MCPツール拡張

- `mcp-fundamentals`
  - IF: `get_fundamentals(tickers, fields) -> DataFrame`
  - MVP取得項目: ROIC、FCF/売上、売上CAGR、EPS成長、ネット負債/EBITDA
  - 取得源: 当面は公開API/OSSクライアント（例: yfinance/yahooquery）→後日有償APIへ差替

- `mcp-news`
  - IF: `get_news(tickers, since) -> list[NewsItem]`
  - MVP: Yahoo Finance/プレスリリースRSS等の要約とメタ（タイトル/URL/日付/ティッカー）
  - 注意: 利用規約順守、出典URL必須、推測禁止

- `mcp-risk`
  - IF: `risk_metrics(returns_df) -> dict`（相関行列、年率ボラ、最大DD）

- `mcp-optimizer`
  - IF: `optimize(candidates, constraints) -> weights`
  - MVP: 平均分散（目標ボラorリターン、地域/銘柄上限、現金許容）

### 19.2 エージェント拡張

- `MacroAgent`
  - 為替/金利/商品感応度→地域初期重みを算出（例: US 45%, JP 25%, EU 20%, CN 10%）
  - 入力: `mcp-fx-commod`（後日）または当面はCSV/固定ルール

- `RiskAgent`
  - 候補群の相関・ボラ・DD算出。制約違反のフラグ付け、分散度推奨

- `RegionAgent`（強化）
  - ファンダ・ニュース・質の指標を `mcp-fundamentals` / `mcp-news` で補完
  - 候補ごとに `evidence` を多様化（ニュースURL/日付、指標値、決算要点）

### 19.3 スコアリング強化

- 指標拡充（4.1に準拠）：
  - Fundamental: ROIC, FCF/売上, 売上CAGR, EPS成長, NetDebt/EBITDA
  - Technical: 1/3/6/12Mモメンタム、出来高トレンド、決算後ギャップ
  - Quality: 希薄化トレンド、保有変化
  - News: 好悪サイン件数/強度（30/90日）
- 正規化: 欠損ロバスト化、外れ値対策（RobustScaler許容）
- 合成: 重みは 0.4/0.35/0.15/0.10 を初期値、将来は学習/ベイズ更新を想定

### 19.4 最適化・制約

- 目的: 目標ボラ最小 or 期待リターン最大（切替）
- 制約: 地域上限（US≤0.5, JP≤0.3, EU≤0.3, CN≤0.2）、銘柄≤0.07、現金0〜10%
- 実装: 平均分散（scipy.optimize）、将来CVaR/Black-Littermanを追加

### 19.5 レポート強化

- 構成（10章）に従い、
  - 採用/不採用理由（上位3指標、根拠URL/日付）
  - マクロ概況（簡潔な要旨）
  - リスク指標（相関マトリクス、想定DDの表/図）
  - 図表（地域配分円グラフ、主要銘柄棒グラフ）
- PDF化は `mcp-report` で後続実装（md→pdf）

### 19.6 受け入れ基準の追補

- 候補の ≥80% にファンダ or ニュース起因の `evidence(url/date or metric)` を最低1件以上
- リスク指標（相関・年率ボラ・最大DD）が `artifacts/` に出力
- 平均分散の制約が1件も違反しない（数値検証をテスト化）

---

## 20. 実行コマンド（拡張後の想定）

```
# 週次実行（全機能）
python -m src.app run --date 2025-08-19 --regions JP,US,EU,CN --output ./artifacts \
  --optimizer mean_variance --target_vol 0.12

# 特色別の段階実行
python -m src.app candidates --regions JP,US,EU,CN
python -m src.app risk --input ./artifacts/candidates_*.json
python -m src.app optimize --input ./artifacts/candidates_*.json --constraints ./constraints.yaml
python -m src.app report --input ./artifacts/portfolio_20250819.json
```


