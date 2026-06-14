# 株式スクリーニングツール

EDINET DB API を使って財務条件と市場指標でスクリーニングし、現在株価のみJ-Quants APIから取得して表示します。結果はSQLiteに蓄積して銘柄を継続追跡できます。

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

> ⚠️ `.env` はGitにコミットしないでください（`.gitignore` で除外済みです）。

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

## 定期実行（cronで毎日自動スクリーニング）

コンテナが起動したまま毎日実行するにはホスト側のcronを使います。

```bash
bash setup_cron.sh
```

対話形式で実行時刻を選べます（毎朝8:00・9:30、毎夕18:00など）。

または `crontab -e` で直接追加する場合:

```
# 毎朝8時（平日のみ）にスクリーニングを実行
0 8 * * 1-5 docker compose -f /path/to/docker-compose.yml exec -T app python screening.py >> /path/to/screening.log 2>&1
```

---

## ファイル構成

```
.
├── app.py              # Streamlit フロントエンド
├── screening.py        # スクリーニングロジック（UIなし）
├── check_history.py    # 履歴確認 CLIツール
├── setup_cron.sh       # 定期実行セットアップ
├── requirements.txt    # Python依存ライブラリ
├── Dockerfile          # Dockerイメージ定義
├── docker-compose.yml  # サービス構成・ボリューム設定
├── .env.example        # APIキー設定テンプレート
├── .gitignore          # .env / .db / .csv を除外
├── README.md           # このファイル
│
├── .env                # ★ 自分で作成（Gitに含めない）
└── exports/            # ★ CSVエクスポート先（自動生成）
```

> SQLiteのDBファイルはDockerの名前付きボリューム（`db_data`）に保存されます。コンテナを削除してもデータは保持されます。

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

- **EDINET DB Freeプラン**: 1日100リクエストまで無料。財務データはDBキャッシュ（30日間）でAPIリクエストを節約します。
- **投資判断**: このツールの出力はあくまで参考情報です。実際の投資判断はご自身の責任で行ってください。

---

## ライセンス

MIT
