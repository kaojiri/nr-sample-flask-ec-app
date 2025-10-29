#!/bin/sh
# Simple PostgreSQL integration script for New Relic Infrastructure Agent
# This script collects basic PostgreSQL metrics and outputs them in New Relic format

# PostgreSQL接続パラメータ（環境変数から取得）
PGHOST=${POSTGRES_HOST:-postgres}
PGPORT=${POSTGRES_PORT:-5432}
PGUSER=${POSTGRES_USER:-postgres}
PGPASSWORD=${POSTGRES_PASSWORD:-postgres}
PGDATABASE=${POSTGRES_DATABASE:-ecdb}

# psqlコマンドが利用可能かチェック
if ! command -v psql >/dev/null 2>&1; then
    # psqlがない場合はPostgreSQLクライアントをインストール
    apk add --no-cache postgresql-client >/dev/null 2>&1
fi

# PostgreSQLに接続してメトリクスを収集
collect_metrics() {
    # データベース統計情報を取得
    STATS=$(PGPASSWORD=$PGPASSWORD psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE -t -c "
        SELECT 
            datname,
            numbackends,
            xact_commit,
            xact_rollback,
            blks_read,
            blks_hit,
            tup_returned,
            tup_fetched,
            tup_inserted,
            tup_updated,
            tup_deleted
        FROM pg_stat_database 
        WHERE datname = '$PGDATABASE';
    " 2>/dev/null)

    if [ $? -eq 0 ] && [ -n "$STATS" ]; then
        # メトリクスをNew Relic形式で出力
        echo "$STATS" | while IFS='|' read -r datname numbackends xact_commit xact_rollback blks_read blks_hit tup_returned tup_fetched tup_inserted tup_updated tup_deleted; do
            # 空白を削除
            datname=$(echo $datname | tr -d ' ')
            numbackends=$(echo $numbackends | tr -d ' ')
            xact_commit=$(echo $xact_commit | tr -d ' ')
            xact_rollback=$(echo $xact_rollback | tr -d ' ')
            blks_read=$(echo $blks_read | tr -d ' ')
            blks_hit=$(echo $blks_hit | tr -d ' ')
            tup_returned=$(echo $tup_returned | tr -d ' ')
            tup_fetched=$(echo $tup_fetched | tr -d ' ')
            tup_inserted=$(echo $tup_inserted | tr -d ' ')
            tup_updated=$(echo $tup_updated | tr -d ' ')
            tup_deleted=$(echo $tup_deleted | tr -d ' ')

            # New Relic形式でメトリクスを出力
            cat << EOF
{
  "name": "com.newrelic.postgresql",
  "protocol_version": "3",
  "integration_version": "1.0.0",
  "data": [
    {
      "entity": {
        "name": "postgresql:$PGHOST:$PGPORT",
        "type": "postgresql-instance"
      },
      "metrics": [
        {
          "name": "PostgreSQLSample",
          "type": "sample",
          "timestamp": $(date +%s)000,
          "attributes": {
            "database": "$datname",
            "host": "$PGHOST",
            "port": $PGPORT,
            "connections": $numbackends,
            "transactionsCommitted": $xact_commit,
            "transactionsRolledBack": $xact_rollback,
            "blocksRead": $blks_read,
            "blocksHit": $blks_hit,
            "tuplesReturned": $tup_returned,
            "tuplesFetched": $tup_fetched,
            "tuplesInserted": $tup_inserted,
            "tuplesUpdated": $tup_updated,
            "tuplesDeleted": $tup_deleted
          }
        }
      ]
    }
  ]
}
EOF
        done
    else
        # 接続エラーの場合
        cat << EOF
{
  "name": "com.newrelic.postgresql",
  "protocol_version": "3",
  "integration_version": "1.0.0",
  "data": [
    {
      "entity": {
        "name": "postgresql:$PGHOST:$PGPORT",
        "type": "postgresql-instance"
      },
      "metrics": [
        {
          "name": "PostgreSQLConnectionError",
          "type": "sample",
          "timestamp": $(date +%s)000,
          "attributes": {
            "error": "Failed to connect to PostgreSQL",
            "host": "$PGHOST",
            "port": $PGPORT
          }
        }
      ]
    }
  ]
}
EOF
    fi
}

# メトリクス収集を実行
collect_metrics