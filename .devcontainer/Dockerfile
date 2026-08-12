# このプロジェクト固有の差分レイヤー。
# 共通ベース（claude-code-devcontainer-template）は Node.js + Claude Code CLI
# のみを持つ言語非依存イメージなので、ここで Python ランタイムと
# プロジェクトの依存パッケージだけを足す。
FROM ghcr.io/jun4696/claude-code-devcontainer-template:latest

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 \
      python3-pip \
      python3-venv \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r /tmp/requirements.txt

USER vscode
