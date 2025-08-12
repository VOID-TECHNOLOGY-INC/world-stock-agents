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
- `artifacts/portfolio_{YYYYMMDD}.json`
- `artifacts/report_{YYYYMMDD}.md`

注意: これは投資助言ではありません。デモ用途のみです。

