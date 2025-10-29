# New Relic PostgreSQL監視設定ガイド

## 概要

このディレクトリには、New Relic Infrastructure AgentによるPostgreSQL監視を設定するためのファイルが含まれています。Docker Compose環境で既存のFlaskアプリケーションに影響を与えることなく、PostgreSQLデータベースの包括的な監視を提供します。

## ファイル構成

```
newrelic/
├── README.md                   # このファイル - 設定ガイド
├── newrelic-infra.yml         # Infrastructure Agent基本設定
└── postgresql-config.yml      # PostgreSQL統合設定
```

## 前提条件

1. **New Relicアカウント**: 有効なNew Relicライセンスキーが必要
2. **Docker Compose**: 既存のDocker Compose環境が動作していること
3. **PostgreSQL**: 監視対象のPostgreSQLデータベースが稼働していること

## セットアップ手順

### 1. 環境変数の設定

`.env`ファイルに以下の環境変数を設定してください：

#### 必須環境変数

```bash
# New Relic Infrastructure Agent設定
NRIA_LICENSE_KEY=your-new-relic-license-key-here
NRIA_DISPLAY_NAME=Flask-EC-Infrastructure

# PostgreSQL接続設定
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DATABASE=ecdb
```

#### オプション環境変数

```bash
# 詳細ログ設定（トラブルシューティング時）
NRIA_VERBOSE=1

# PostgreSQL統合設定のオーバーライド
NRIA_POSTGRESQL_COLLECTION_LIST=ALL
NRIA_POSTGRESQL_COLLECT_DB_LOCK_METRICS=true
NRIA_POSTGRESQL_COLLECT_BLOAT_METRICS=true
NRIA_POSTGRESQL_QUERY_PERFORMANCE_MONITORING=true
NRIA_POSTGRESQL_COLLECTION_INTERVAL=60
NRIA_POSTGRESQL_MAX_QUERY_LENGTH=4096
```

### 2. Docker Composeサービスの起動

```bash
# Infrastructure Agentコンテナを含む全サービスの起動
docker-compose up -d

# Infrastructure Agentのログ確認
docker-compose logs -f newrelic-infra
```

### 3. 動作確認

Infrastructure Agentが正常に動作していることを確認：

```bash
# コンテナの状態確認
docker-compose ps newrelic-infra

# ログでエラーがないことを確認
docker-compose logs newrelic-infra | grep -i error
```

## 環境変数詳細説明

### Infrastructure Agent設定

| 環境変数 | 説明 | デフォルト値 | 必須 |
|---------|------|-------------|------|
| `NRIA_LICENSE_KEY` | New Relicライセンスキー | なし | ✓ |
| `NRIA_DISPLAY_NAME` | エージェントの表示名 | なし | ✓ |
| `NRIA_VERBOSE` | 詳細ログの有効化（0または1） | 0 | |

### PostgreSQL接続設定

| 環境変数 | 説明 | デフォルト値 | 必須 |
|---------|------|-------------|------|
| `POSTGRES_HOST` | PostgreSQLホスト名 | postgres | ✓ |
| `POSTGRES_PORT` | PostgreSQLポート番号 | 5432 | ✓ |
| `POSTGRES_USER` | PostgreSQLユーザー名 | postgres | ✓ |
| `POSTGRES_PASSWORD` | PostgreSQLパスワード | postgres | ✓ |
| `POSTGRES_DATABASE` | 監視対象データベース名 | ecdb | ✓ |

### PostgreSQL統合オプション設定

| 環境変数 | 説明 | デフォルト値 |
|---------|------|-------------|
| `NRIA_POSTGRESQL_COLLECTION_LIST` | 収集するメトリクスの範囲 | ALL |
| `NRIA_POSTGRESQL_COLLECT_DB_LOCK_METRICS` | ロックメトリクスの収集 | true |
| `NRIA_POSTGRESQL_COLLECT_BLOAT_METRICS` | ブロートメトリクスの収集 | true |
| `NRIA_POSTGRESQL_QUERY_PERFORMANCE_MONITORING` | クエリパフォーマンス監視 | true |
| `NRIA_POSTGRESQL_COLLECTION_INTERVAL` | メトリクス収集間隔（秒） | 60 |
| `NRIA_POSTGRESQL_MAX_QUERY_LENGTH` | 記録するクエリの最大長 | 4096 |

## 収集されるメトリクス

### データベースレベルメトリクス

- **接続数**: アクティブな接続数、最大接続数
- **トランザクション**: コミット数、ロールバック数、実行中トランザクション数
- **データベースサイズ**: 各データベースの使用容量
- **パフォーマンス**: キャッシュヒット率、ディスクI/O統計

### テーブルレベルメトリクス

- **テーブルサイズ**: 各テーブルの行数、ディスク使用量
- **インデックス使用状況**: インデックススキャン数、効率性
- **Vacuum/Analyze統計**: 最終実行時刻、実行回数

### クエリパフォーマンスメトリクス

- **実行統計**: クエリ実行回数、平均実行時間
- **リソース使用量**: CPU時間、I/O統計
- **遅いクエリ**: 実行時間の長いクエリの特定

## New Relicダッシュボードでの確認方法

### 1. Infrastructure監視の確認

1. New Relicにログイン
2. **Infrastructure** → **Hosts** に移動
3. `Flask-EC-Infrastructure`という名前のホストを確認
4. PostgreSQLメトリクスが表示されていることを確認

### 2. Database監視の確認

1. **Databases** セクションに移動
2. PostgreSQLインスタンスが表示されていることを確認
3. 以下のメトリクスが収集されていることを確認：
   - Database connections
   - Transaction throughput
   - Query performance
   - Table and index statistics

### 3. カスタムダッシュボードの作成

推奨するダッシュボードウィジェット：

```sql
-- アクティブ接続数
SELECT latest(postgresql.connections.active) FROM PostgreSQLSample WHERE displayName = 'Flask-EC-Infrastructure'

-- データベースサイズ
SELECT latest(postgresql.database.size) FROM PostgreSQLSample WHERE displayName = 'Flask-EC-Infrastructure' FACET database

-- 遅いクエリ（上位10件）
SELECT average(postgresql.query.meanTime) FROM PostgreSQLSample WHERE displayName = 'Flask-EC-Infrastructure' FACET query LIMIT 10
```

### 4. アラート設定

重要なメトリクスに対するアラート設定例：

- **接続数アラート**: アクティブ接続数が最大接続数の80%を超えた場合
- **データベースサイズアラート**: データベースサイズが急激に増加した場合
- **遅いクエリアラート**: 平均クエリ実行時間が閾値を超えた場合

## トラブルシューティング

### よくある問題と解決方法

#### 1. Infrastructure Agentが起動しない

**症状**: コンテナが起動直後に停止する

**確認事項**:
```bash
# ログの確認
docker-compose logs newrelic-infra

# 環境変数の確認
docker-compose exec newrelic-infra env | grep NRIA
```

**解決方法**:
- `NRIA_LICENSE_KEY`が正しく設定されているか確認
- ライセンスキーが有効であることをNew Relicコンソールで確認

#### 2. PostgreSQLに接続できない

**症状**: "connection refused"または"authentication failed"エラー

**確認事項**:
```bash
# PostgreSQLコンテナの状態確認
docker-compose ps postgres

# ネットワーク接続の確認
docker-compose exec newrelic-infra ping postgres

# PostgreSQL接続テスト
docker-compose exec newrelic-infra psql -h postgres -U postgres -d ecdb -c "SELECT version();"
```

**解決方法**:
- PostgreSQL接続情報（ホスト名、ポート、認証情報）を確認
- PostgreSQLコンテナが完全に起動するまで待機
- `depends_on`設定でPostgreSQLの健全性チェックを確認

#### 3. メトリクスがNew Relicに表示されない

**症状**: Infrastructure AgentとPostgreSQLの接続は成功するが、メトリクスが表示されない

**確認事項**:
```bash
# 詳細ログの有効化
# .envファイルでNRIA_VERBOSE=1に設定してコンテナを再起動
docker-compose restart newrelic-infra

# ログでメトリクス送信を確認
docker-compose logs newrelic-infra | grep -i "sending"
```

**解決方法**:
- New Relicライセンスキーが正しいアカウントのものか確認
- ファイアウォールやプロキシ設定を確認
- New Relicのサービス状況を確認

#### 4. Query Performance Monitoringが動作しない

**症状**: 基本メトリクスは収集されるが、クエリパフォーマンスデータが表示されない

**確認事項**:
```bash
# pg_stat_statementsの有効化確認
docker-compose exec postgres psql -U postgres -d ecdb -c "SELECT * FROM pg_stat_statements LIMIT 1;"
```

**解決方法**:
- PostgreSQLで`pg_stat_statements`拡張が有効になっているか確認
- 必要に応じてPostgreSQLの設定を更新：
  ```sql
  -- PostgreSQLコンテナ内で実行
  CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
  ```

### ログレベルの調整

トラブルシューティング時は、より詳細なログを有効にできます：

```bash
# .envファイルで設定
NRIA_VERBOSE=1

# または、newrelic-infra.ymlで設定
log_level: debug
verbose: 1
```

### パフォーマンスの最適化

監視によるオーバーヘッドを最小限に抑えるための設定：

```bash
# 収集間隔の調整（秒単位）
NRIA_POSTGRESQL_COLLECTION_INTERVAL=120  # デフォルト60秒から120秒に変更

# 収集するメトリクスの制限
NRIA_POSTGRESQL_COLLECTION_LIST=DATABASE,TABLE  # ALLの代わりに特定のメトリクスのみ
```

## サポートとリソース

- **New Relic Documentation**: [PostgreSQL monitoring](https://docs.newrelic.com/docs/infrastructure/host-integrations/host-integrations-list/postgresql-monitoring-integration/)
- **Infrastructure Agent Documentation**: [New Relic Infrastructure Agent](https://docs.newrelic.com/docs/infrastructure/install-infrastructure-agent/)
- **トラブルシューティングガイド**: [Infrastructure Agent troubleshooting](https://docs.newrelic.com/docs/infrastructure/install-infrastructure-agent/troubleshooting/)

## 設定ファイルの詳細

### newrelic-infra.yml

Infrastructure Agentの基本設定ファイル。ライセンスキー、ログレベル、メトリクス収集間隔などを設定します。

### postgresql-config.yml

PostgreSQL統合の詳細設定ファイル。データベース接続情報、収集するメトリクスの種類、Query Performance Monitoringの設定を含みます。

両ファイルとも環境変数による設定のオーバーライドをサポートしており、異なる環境（開発、ステージング、本番）での柔軟な設定変更が可能です。