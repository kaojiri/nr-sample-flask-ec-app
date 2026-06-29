FROM seleniarm/standalone-chromium:latest

USER root

WORKDIR /app

# pip をインストール（ensurepip — ネットワーク不要）
RUN python3 -m ensurepip --upgrade 2>/dev/null || \
    (apt-get update && apt-get install -y --no-install-recommends python3-pip && rm -rf /var/lib/apt/lists/*) || \
    (curl -ksSL https://bootstrap.pypa.io/get-pip.py | python3)

# pip を最新に（失敗しても続行）
RUN python3 -m pip install --upgrade pip 2>/dev/null || true

# 依存パッケージインストール
COPY requirements.txt .
RUN python3 -m pip install --no-cache-dir --break-system-packages -r requirements.txt 2>/dev/null || \
    python3 -m pip install --no-cache-dir -r requirements.txt

# アプリケーションコードコピー
COPY . .

# データディレクトリ作成
RUN mkdir -p /app/data/results /app/logs

# APIポート公開
EXPOSE 8081

# ヘルスチェック
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -kf http://localhost:8081/health || exit 1

# Selenium起動スクリプトと並行してPythonアプリ起動
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
