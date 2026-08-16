# 株式スクリーニングツール

EDINET DB API を使って財務条件と市場指標でスクリーニングし、現在株価のみJ-Quants APIから取得して表示します。実行結果はその場でDataFrame表示・CSVダウンロードのみで、DBへの蓄積（実行履歴）は行いません。EDINET DB無料枠のレート制限を節約するための財務データキャッシュだけは、ローカルのSQLiteファイルに保持します。

---

## スクリーニング条件（デフォルト値）

| 条件 | デフォルト | データソース |
|---|---|---|
| 流動資産 > 負債合計 | 常に適用 | EDINET DB（有報） |
| PER | 8倍 以下 | EDINET DB |
| PBR | 0.8倍 以下 | EDINET DB |
| 時価総額 | 500億円 以下 | EDINET DB |
| 配当利回り | 4%以上 | EDINET DB |
| 現在株価 | 表示のみ | J-Quants |

> 条件はUI上でその場で変更できます。

---

## 必要なもの

- Docker & Docker Compose
- [EDINET DB](https://edinetdb.jp/developers) のAPIキー（無料: 1日100回）
- [J-Quants](https://jpx-jquants.com/) のAPIキー（現在株価表示用）

---

## セットアップ

### 1. リポジトリをクローン

```bash
git clone https://github.com/your-name/your-repo.git
cd your-repo
```

### 2. APIキーを設定

```bash
cp .env.example .env
```

`.env` をエディタで開き、実際のAPIキーを入力します。

```
EDINETDB_API_KEY=edb_実際のキーを貼る
JQUANTS_API_KEY=実際のキーを貼る
```

> `.env` はGitにコミットしないでください（`.gitignore` で除外済みです）。Renderでは `EDINETDB_API_KEY`、`JQUANTS_API_KEY` を環境変数として入力します。

### 3. Dockerで起動

```bash
docker compose up --build
```

ブラウザで [http://localhost:8501](http://localhost:8501) を開きます。

---

## 画面構成

### 🔍 スクリーニング実行

スライダーや数値入力で条件を調整し「実行」を押すだけです。進捗バーで処理状況を確認できます。結果はそのままDataFrameで表示され、CSVダウンロードボタンが出ます（今回の実行結果のみ。DBへの蓄積は行いません）。

---

## Renderでの本番デプロイ

1. Render Blueprintでこのリポジトリを同期します。
2. Renderの環境変数に `EDINETDB_API_KEY`、`JQUANTS_API_KEY` を入力します。

外部DBのセットアップは不要です。ただしRender無料プランは永続ディスクを付けない限りコンテナ再起動でローカルファイルが消えるため、財務データキャッシュ（SQLite）は「ベストエフォート」の節約用途になります（消えても次回アクセス時に再取得されるだけで、動作自体には影響しません）。

---

## ファイル構成

```
.
├── app.py              # Streamlit フロントエンド
├── screening.py        # スクリーニングロジック（UIなし）
├── requirements.txt    # Python依存ライブラリ
├── Dockerfile          # Dockerイメージ定義
├── docker-compose.yml  # アプリ構成
├── render.yaml         # Render Blueprint
├── .env.example        # APIキー設定テンプレート
├── .gitignore          # .env / .db / .csv を除外
├── README.md           # このファイル
│
├── .env                # ★ 自分で作成（Gitに含めない）
├── data/                # ★ 財務データキャッシュ（SQLite、自動生成）
└── exports/             # ★ CSVエクスポート先（自動生成）
```

---

## Dockerを使わない場合（ローカル直接実行）

```bash
pip install -r requirements.txt
streamlit run app.py        # WebUI
```

---

## 注意事項

- **EDINET DB Freeプラン**: 1日100リクエストまで無料。財務データはローカルSQLiteキャッシュ（30日間）でAPIリクエストを節約します。
- **投資判断**: このツールの出力はあくまで参考情報です。実際の投資判断はご自身の責任で行ってください。

---

## ライセンス

MIT
