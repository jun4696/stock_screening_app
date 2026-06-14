# ---- ベースイメージ ----
FROM python:3.12-slim

# タイムゾーン設定（日本時間）
ENV TZ=Asia/Tokyo
RUN apt-get update && apt-get install -y --no-install-recommends tzdata curl \
    && rm -rf /var/lib/apt/lists/*

# 作業ディレクトリ
WORKDIR /app

# 依存ライブラリを先にインストール（レイヤーキャッシュ活用）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリコードをコピー
COPY screening.py app.py check_history.py ./

# SQLiteのデータ保存用ディレクトリを作成
RUN mkdir -p /data

# Streamlitのデフォルトポート
EXPOSE 8501

# ヘルスチェック
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# 起動コマンド
CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
