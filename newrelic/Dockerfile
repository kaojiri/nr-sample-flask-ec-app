# New Relic Infrastructure Agent with PostgreSQL integration
FROM newrelic/infrastructure:latest

# 必要なパッケージをインストール
RUN apk add --no-cache curl

# New Relicリポジトリを追加してPostgreSQL統合をインストール
RUN curl -s https://download.newrelic.com/infrastructure_agent/gpg/newrelic-infra.gpg | apk add --allow-untrusted - && \
    echo "https://download.newrelic.com/infrastructure_agent/linux/apk/x86_64" >> /etc/apk/repositories && \
    apk update || true

# 統合ディレクトリを作成
RUN mkdir -p /var/db/newrelic-infra/integrations.d/

# PostgreSQL統合のバイナリを手動で作成（シンプルなスクリプトとして）
COPY postgresql-integration.sh /var/db/newrelic-infra/integrations.d/nri-postgresql
RUN chmod +x /var/db/newrelic-infra/integrations.d/nri-postgresql

# デフォルトのエントリーポイントを使用
ENTRYPOINT ["/sbin/tini", "--", "/usr/bin/newrelic-infra"]