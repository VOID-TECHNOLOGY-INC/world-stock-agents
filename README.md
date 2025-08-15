# 世界株式エージェント（MVP）

要件は `doc/specification.md` を参照。MVPは JP/US のCSVダミーデータを用いて、特徴量→スコア→候補JSON→最終ポートフォリオJSON→Markdownレポを生成します。

## セットアップ

```bash
# 仮想環境の作成とアクティベート
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# または
.venv\Scripts\activate  # Windows

# 依存関係のインストール
pip install -r requirements.txt

# 環境変数の設定
cp .env.example .env  # OPENAI_API_KEY を設定
```

## 基本的な使い方

### 1. エンドツーエンド実行（推奨）

週次レポートの完全な生成（候補選定→最適化→レポート生成）：

```bash
python -m src.app run --date 2025-08-12 --regions JP,US --output ./artifacts
```

**オプション:**
- `--date`: 実行日（デフォルト: 今日）
- `--regions`: 対象地域（CSV形式、デフォルト: JP,US）
- `--output`: 出力先ディレクトリ（デフォルト: ./artifacts）
- `--top-n`: 各地域の上位候補数（デフォルト: 50）
- `--risk-aversion`: リスク許容度（大きいほどリターン重視、デフォルト: 0.0）
- `--target-vol`: 年率ボラ上限（例: 0.18、デフォルト: 制約なし）
- `--target`: 目的関数（min_vol / max_return、デフォルト: min_vol）
- `--macro-csv`: マクロ初期重みCSVのパス（region,weight）

### オプションの詳細な使い方

#### `--top-n` オプション
各地域から選定する候補銘柄の数を指定します。

```bash
# 各地域から上位20銘柄を選定
python -m src.app run --top-n 20 --regions JP,US

# 各地域から上位100銘柄を選定（より多くの候補から選択）
python -m src.app run --top-n 100 --regions JP,US,EU

# 候補選定のみで上位30銘柄を取得
python -m src.app candidates --top-n 30 --regions JP,US
```

**推奨値:**
- **保守的**: 20-30（高品質な銘柄のみ）
- **標準**: 50（バランスの取れた選択）
- **積極的**: 80-100（より多くの選択肢）

#### `--risk-aversion` オプション
リスクとリターンのトレードオフを制御します。

```bash
# リスク最小化（デフォルト）
python -m src.app run --risk-aversion 0.0

# リスクとリターンのバランス
python -m src.app run --risk-aversion 0.5

# リターン最大化重視
python -m src.app run --risk-aversion 1.0

# より積極的なリターン追求
python -m src.app run --risk-aversion 2.0
```

#### `--target-vol` オプション
年率ボラティリティの上限を設定します。

```bash
# 年率15%のボラ上限を設定
python -m src.app run --target-vol 0.15

# 年率20%のボラ上限を設定
python -m src.app run --target-vol 0.20

# ボラ制約なし（デフォルト）
python -m src.app run --target-vol None
```

#### `--target` オプション
最適化の目的関数を指定します。

```bash
# ボラティリティ最小化（デフォルト）
python -m src.app run --target min_vol

# リターン最大化
python -m src.app run --target max_return

# リスク許容度と組み合わせて使用
python -m src.app run --target max_return --risk-aversion 0.5
```

#### `--macro-csv` オプション
地域配分の初期重みをCSVファイルで指定します。

```bash
# カスタム地域重みを指定
python -m src.app run --macro-csv ./data/macro_weights.csv

# CSVファイルの形式例:
# region,weight
# JP,0.3
# US,0.5
# EU,0.2
```

#### 複数オプションの組み合わせ例

```bash
# 保守的な設定
python -m src.app run \
  --top-n 30 \
  --risk-aversion 0.0 \
  --target-vol 0.15 \
  --target min_vol \
  --regions JP,US

# 積極的な設定
python -m src.app run \
  --top-n 80 \
  --risk-aversion 1.0 \
  --target max_return \
  --regions JP,US,EU,CN

# バランス型の設定
python -m src.app run \
  --top-n 50 \
  --risk-aversion 0.5 \
  --target-vol 0.18 \
  --regions JP,US
```

### 2. 候補選定のみ

地域別エージェントを実行し、候補JSONを出力：

```bash
python -m src.app candidates --regions JP,US --date 2025-08-12 --output ./artifacts
```

### 3. レポート生成のみ

既存のポートフォリオJSONからMarkdownレポートを生成：

```bash
python -m src.app report --input ./artifacts/portfolio_20250812.json --output ./artifacts
```

## Makefileを使った簡単実行

### 週次実行
```bash
make run-weekly DATE=2025-08-12 REGIONS=JP,US
```

### 候補選定のみ
```bash
make candidates DATE=2025-08-12 REGIONS=JP,US
```

### レポート生成のみ
```bash
make report DATE=2025-08-12
```

## サポート地域

- **JP**: 日本（TOPIX500相当）
- **US**: 米国（S&P500 + NASDAQ100相当）
- **EU**: 欧州（STOXX600相当）
- **CN**: 中国（CSI300 + 香港相当）

各地域のユニバース定義は `data/universe/*.csv` を参照。yfinanceで実データ（終値・出来高）を取得します。

## 出力ファイル

実行後、以下のファイルが生成されます：

### 候補ファイル
- `artifacts/candidates_{REGION}_{YYYYMMDD}.json` - 各地域の総合スコア上位候補
- `artifacts/growth_{REGION}_{YYYYMMDD}.json` - 各地域の成長スコア上位候補

### ポートフォリオ・リスクファイル
- `artifacts/portfolio_{YYYYMMDD}.json` - 最適化されたポートフォリオ配分
- `artifacts/risk_{YYYYMMDD}.json` - リスク指標（相関・ボラ・ドローダウン）

### レポート・可視化ファイル
- `artifacts/report_{YYYYMMDD}.md` - Markdown形式の投資レポート
- `artifacts/corr_{YYYYMMDD}.png` - 相関ヒートマップ
- `artifacts/alloc_{YYYYMMDD}.png` - 配分円グラフ

## 成長株リスト（growth_{REGION}_{YYYYMMDD}.json）

- **概要**: 各地域の候補とは別に、成長性を重視した上位銘柄リストを出力します。
- **出力場所**: `artifacts/growth_{REGION}_{YYYYMMDD}.json`
- **選定基準**: `score_growth` の降順
  - `score_growth = mean(growth_revenue_cagr, growth_eps_growth)`
  - いずれも正規化後の値（0〜1）を平均
- **含まれる主な項目**:
  - `ticker`, `name`
  - `score_overall`（総合スコア）
  - `score_breakdown`: `fundamental`, `technical`, `quality`, `news`, `growth`
  - `thesis`, `risks`, `evidence`

## テスト実行

```bash
# 全テスト実行
python -m pytest tests/

# 特定のテストファイル実行
python -m pytest tests/unit/test_app_cli_minimal.py

# カバレッジ付きテスト実行
python -m pytest tests/ --cov=src --cov-report=html
```

## 実装メモ

- スコア計算は `src/scoring/scoring.py` の `score_candidates` で実施。
- 成長特徴量（`revenue_cagr`, `eps_growth`）は `src/scoring/features.py` の `merge_fundamentals` で `growth_*` 列にマージ。
- 総合スコアへの影響は `ScoreWeights.growth` で制御（初期値 0.0 のため既存の総合スコアには影響なし）。

## 注意事項

**⚠️ これは投資助言ではありません。デモ用途のみです。**

- 本システムは教育・研究目的で開発されています
- 実際の投資判断には、専門家の助言を必ず受けてください
- 過去のパフォーマンスは将来の結果を保証するものではありません

