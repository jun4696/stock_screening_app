# 株式スクリーニングツール

EDINET DB API を使って財務条件と市場指標でスクリーニングし、現在株価のみJ-Quants APIから取得して表示します。結果はPostgresに蓄積して銘柄を継続追跡できます。Render本番ではSupabase Postgresを使う想定です。

---

## スクリーニング条件（デフォルト値）

| 条件 | デフォルト | データソース |
|---|---|---|
| 流動資産 > 負債合計 | 常に適用 | EDINET DB（有報） |
| PER | 8倍 以下 | EDINET DB |
| PBR | 0.8倍 以下 | EDINET DB |
| 時価総額 | 500億円 以下 | EDINET DB |
| 現在株価 | 表示のみ | J-Quants |

> 条件はUI上でその場で変更できます。

---

## 必要なもの

- Docker & Docker Compose
- Postgres（ローカルDockerでは自動起動。本番はSupabase推奨）
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

# 本番(Render)ではSupabaseの接続文字列を設定
DATABASE_URL=postgresql://postgres.<project-ref>:<password>@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres?sslmode=require
```

> `.env` はGitにコミットしないでください（`.gitignore` で除外済みです）。Renderでは `EDINETDB_API_KEY`、`JQUANTS_API_KEY`、`DATABASE_URL` を環境変数として入力します。

### 3. Dockerで起動

```bash
docker compose up --build
```

ブラウザで [http://localhost:8501](http://localhost:8501) を開きます。

---

## 画面構成

### 🔍 スクリーニング実行

スライダーや数値入力で条件を調整し「実行」を押すだけです。進捗バーで処理状況を確認できます。結果はそのままDataFrameで表示され、CSVダウンロードボタンが出ます。

### 📊 履歴・銘柄追跡

- **実行履歴サマリー**: 過去の実行日ごとのヒット数をグラフで確認。連続ヒットランキングも表示。
- **日別結果**: 過去の特定日の結果を選んで確認・CSV出力。
- **銘柄別追跡**: 証券コードで検索して出現履歴と現在株価を表示。

### 📥 CSVダウンロード

全期間の蓄積データを一括でCSVダウンロードできます。

---

## Render + Supabase での本番設定

1. Supabaseで新規プロジェクトを作成します。
2. Project Settings → Database から接続文字列を取得します。Renderから接続するため `sslmode=require` を付けてください。
3. Render Blueprintでこのリポジトリを同期します。
4. Renderの環境変数に `EDINETDB_API_KEY`、`JQUANTS_API_KEY`、`DATABASE_URL` を入力します。

Supabase Free の Nano は推奨DBサイズ500MB、DB接続60、Pooler 200です。個人利用や小規模な履歴保存なら十分ですが、長期運用で財務キャッシュと実行履歴を無制限に溜める設計ではありません。

---

## ファイル構成

```
.
├── app.py              # Streamlit フロントエンド
├── screening.py        # スクリーニングロジック（UIなし）
├── check_history.py    # 履歴確認 CLIツール
├── requirements.txt    # Python依存ライブラリ
├── Dockerfile          # Dockerイメージ定義
├── docker-compose.yml  # アプリ + ローカルPostgres構成
├── render.yaml         # Render Blueprint
├── .env.example        # APIキー設定テンプレート
├── .gitignore          # .env / .db / .csv を除外
├── README.md           # このファイル
│
├── .env                # ★ 自分で作成（Gitに含めない）
└── exports/            # ★ CSVエクスポート先（自動生成）
```

> ローカル開発ではPostgresのデータがDockerの名前付きボリューム（`pg_data`）に保存されます。Render本番ではSupabase Postgresに保存します。

---

## CLIで直接操作する場合

```bash
# コンテナ内でCLI実行
docker compose exec app python check_history.py
docker compose exec app python check_history.py --code 7203
docker compose exec app python check_history.py --streak 3
docker compose exec app python check_history.py --all
```

---

## Dockerを使わない場合（ローカル直接実行）

```bash
pip install -r requirements.txt
streamlit run app.py        # WebUI
python screening.py         # CLIでスクリーニング実行
python check_history.py     # CLI履歴確認
```

---

## 注意事項

- **EDINET DB Freeプラン**: 1日100リクエストまで無料。財務データはPostgresキャッシュ（30日間）でAPIリクエストを節約します。
- **Supabase Free**: 小規模利用には十分ですが、500MBを超える履歴保存や高頻度アクセスには向きません。
- **投資判断**: このツールの出力はあくまで参考情報です。実際の投資判断はご自身の責任で行ってください。

---

## ライセンス

MIT
