FROM postgres:15

# 必要なパッケージをインストール
RUN apt-get update && apt-get install -y \
    postgresql-15-pg-wait-sampling \
    wget \
    git \
    build-essential \
    postgresql-server-dev-15 \
    && rm -rf /var/lib/apt/lists/*

# pg_stat_monitorをgit cloneでインストール（バージョン2.1.1を指定）
RUN cd /tmp \
    && git clone https://github.com/percona/pg_stat_monitor.git \
    && cd pg_stat_monitor \
    && git checkout 2.1.1 \
    && make USE_PGXS=1 \
    && make USE_PGXS=1 install \
    && cd / \
    && rm -rf /tmp/pg_stat_monitor

# カスタム設定ファイルをコピー
COPY postgresql.conf /etc/postgresql/postgresql.conf

# 初期化スクリプトをコピー
COPY init-scripts/ /docker-entrypoint-initdb.d/

# PostgreSQLの設定ファイルを使用するようにコマンドを設定
CMD ["postgres", "-c", "config_file=/etc/postgresql/postgresql.conf"]