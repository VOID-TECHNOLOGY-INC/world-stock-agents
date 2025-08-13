世界株式エージェント（MVP）

要件は `doc/specification.md` を参照。MVPは JP/US のCSVダミーデータを用いて、特徴量→スコア→候補JSON→最終ポートフォリオJSON→Markdownレポを生成します。

セットアップ:

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # OPENAI_API_KEY を設定
```

実行:

```
python -m src.app run --date 2025-08-12 --regions JP,US --output ./artifacts
```

サポート地域: JP/US/EU/CN（`data/universe/*.csv` を参照）。yfinanceで実データ（終値・出来高）を取得します。

成果物:

- `artifacts/candidates_{REGION}_{YYYYMMDD}.json`
- `artifacts/growth_{REGION}_{YYYYMMDD}.json`
- `artifacts/portfolio_{YYYYMMDD}.json`
- `artifacts/report_{YYYYMMDD}.md`

注意: これは投資助言ではありません。デモ用途のみです。

## 成長株リスト（growth_{REGION}_{YYYYMMDD}.json）

- 概要: 各地域の候補とは別に、成長性を重視した上位銘柄リストを出力します。
- 出力場所: `artifacts/growth_{REGION}_{YYYYMMDD}.json`
- 選定基準: `score_growth` の降順
  - `score_growth = mean(growth_revenue_cagr, growth_eps_growth)`
  - いずれも正規化後の値（0〜1）を平均
- 含まれる主な項目:
  - `ticker`, `name`
  - `score_overall`（総合スコア）
  - `score_breakdown`: `fundamental`, `technical`, `quality`, `news`, `growth`
  - `thesis`, `risks`, `evidence`

### 使い方

```bash
python -m src.app run --date 2025-08-12 --regions JP,US --output ./artifacts
```

実行後、以下が作成されます:

- `candidates_{REGION}_{YYYYMMDD}.json`（総合スコア上位）
- `growth_{REGION}_{YYYYMMDD}.json`（成長スコア上位）

### 実装メモ

- スコア計算は `src/scoring/scoring.py` の `score_candidates` で実施。
- 成長特徴量（`revenue_cagr`, `eps_growth`）は `src/scoring/features.py` の `merge_fundamentals` で `growth_*` 列にマージ。
- 総合スコアへの影響は `ScoreWeights.growth` で制御（初期値 0.0 のため既存の総合スコアには影響なし）。

