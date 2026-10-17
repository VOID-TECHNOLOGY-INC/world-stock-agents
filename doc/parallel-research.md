# Parallel Search MCP で候補銘柄の根拠を確認する

候補JSONの `thesis` や `risks` を読む際に、企業の決算発表やリスク情報を追加で調べるための独立したサンプルです。[Parallel Search MCP](https://docs.parallel.ai/integrations/mcp/search-mcp) の無料・匿名エンドポイントを使い、Fast モードのウェブ検索と、選んだURLのページ取得を実行します。Parallel のアカウントやAPIキーは不要です。無料枠には利用制限があります。

このサンプルは手動で実行します。既存の `src.app`、OpenAI / Perplexity の選択、ニュース取得、スコア、候補JSONやレポートは変更しません。取得した情報も自動では取り込みません。

## 実行環境

Python 3.11 以上と [uv](https://docs.astral.sh/uv/getting-started/installation/) を用意し、リポジトリのルートから実行します。`uv run` がスクリプト内で宣言した `mcp` と `httpx` を専用環境にインストールするため、このサンプルだけならメインの `requirements.txt` のインストールは不要です。`.env` や保存済みのAPIキーは読み込みません。

```bash
uv run examples/parallel_research.py --help
```

## 1. 候補の一次資料を検索する

たとえば `candidates_JP_YYYYMMDD.json` 内のトヨタ自動車（`7203.T`）について、企業名とティッカーを組み合わせて決算・業績見通しの資料を探します。以下のクエリは調査目的に合わせて変更してください。

```bash
mkdir -p artifacts
uv run examples/parallel_research.py search \
  --objective "Find Toyota Motor (7203.T) latest earnings release and outlook. Prefer investor relations primary sources with publication dates." \
  --query "Toyota Motor latest earnings outlook" \
  --query "トヨタ 決算 業績見通し IR" \
  > artifacts/toyota_search.json
```

成功時はMCPの結果をJSONとして標準出力に出します。`content` 内のテキストや、返される場合は `structuredContent` から、URL・公開日・抜粋を確認します。検索結果に含まれる日付や資料の対象期間は原文でも確認してください。

## 2. 選んだページを読む

検索結果から選んだURLを `--url` に渡します。下記のIRトップページを、実際に見つけた決算資料などのURLに置き換えると、より絞った確認ができます。

```bash
uv run examples/parallel_research.py fetch \
  --url "https://global.toyota/en/ir/" \
  --objective "Find earnings releases, outlook and disclosed business risks." \
  > artifacts/toyota_fetch.json
```

`--url` は最大20件まで繰り返せます。`fetch --objective` は200文字以内です。同じ調査の呼び出しをまとめる場合は、サブコマンドの前に `--session-id YOUR_RESEARCH_ID` を指定し、その調査中は同じID（100文字以内）を再利用してください。

URL、公開日、決算の対象期間、確認した事実、見通しや推測を区別して調査メモに残します。過去日付の週次レポートを検証する場合、検索結果にはその時点で未公表の情報も含まれ得るため、当時利用可能だった資料だけを使います。検索や取得の抜粋だけで業績数値や投資判断を確定しないでください。これは投資助言ではなく、教育・研究用の補助ツールです。

## エラーとテスト

通信・MCPツールエラーやタイムアウトでは標準エラーに理由を表示し、終了コード1を返します。処理全体の上限は90秒、個々の通信・応答待ちは30秒です。Ctrl+C で中断すると終了コード130を返します。リダイレクト先のファイルは失敗時にも作られるため、終了コードと内容を確認してください。利用制限が返された場合は案内された時間まで待ち、IDを変えて再試行しないでください。

ネットワークを使わず、実際のMCP SDKにHTTP応答を渡してサンプルを検証できます。

```bash
uv run --with "mcp>=1.30,<2" --with "httpx>=0.27,<1" --with pytest \
  python -m pytest tests/unit/test_parallel_research.py
```

通常の開発環境で追加依存がない場合、このサンプル用テストはスキップされます。
