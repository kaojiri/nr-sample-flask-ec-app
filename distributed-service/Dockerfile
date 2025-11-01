# Python 3.9ベースイメージを使用
FROM python:3.9-slim

# 作業ディレクトリを設定
WORKDIR /app

# システムの依存関係をインストール
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Pythonの依存関係ファイルをコピー
COPY requirements.txt .

# Pythonパッケージをインストール
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードをコピー
COPY . .

# New Relic設定ファイルをコピー
COPY newrelic.ini .

# 起動スクリプトをコピーして実行可能にする
COPY start.sh .
RUN chmod +x /app/start.sh

# ポート5000を公開
EXPOSE 5000

# 環境変数を設定
ENV FLASK_APP=app.py
ENV FLASK_ENV=development
ENV NEW_RELIC_CONFIG_FILE=newrelic.ini

# アプリケーションを起動
CMD ["/app/start.sh"]