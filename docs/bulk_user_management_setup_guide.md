# 一括ユーザー管理システム 設定ガイド

## 概要

このガイドでは、一括ユーザー管理システムの初期設定から運用まで、段階的に説明します。

## 前提条件

### システム要件

- Python 3.8以上
- Flask 2.0以上
- SQLAlchemy 1.4以上
- PostgreSQL または SQLite
- 最低4GB RAM（1000ユーザー作成時）

### 依存関係

```bash
pip install flask flask-sqlalchemy flask-login flask-migrate
pip install requests python-dotenv
```

## 初期設定

### 1. データベース設定

#### SQLiteの場合（開発環境）

```bash
# 環境変数設定
export DATABASE_URL="sqlite:///instance/test.db"
export SECRET_KEY="your-secret-key-here"
```

#### PostgreSQLの場合（本番環境）

```bash
# 環境変数設定
export DATABASE_URL="postgresql://username:password@localhost/dbname"
export SECRET_KEY="your-production-secret-key"
```

### 2. データベースマイグレーション

```bash
# マイグレーション実行
flask db upgrade

# 必要に応じて初期データ作成
python scripts/init-db.py
```

### 3. 設定ファイルの作成

#### Main Application設定

`.env`ファイルを作成：

```env
# データベース設定
DATABASE_URL=sqlite:///instance/test.db
SECRET_KEY=your-secret-key-here

# 一括ユーザー管理設定
BULK_USER_MAX_COUNT=1000
BULK_USER_DEFAULT_BATCH_SIZE=100
BULK_USER_DEFAULT_PASSWORD=TestPass123!

# Load Tester連携設定
LOAD_TESTER_URL=http://localhost:8080
LOAD_TESTER_API_KEY=your-api-key
SYNC_ENABLED=true
SYNC_TIMEOUT=30

# ログ設定
LOG_LEVEL=INFO
LOG_FILE=logs/bulk_user_management.log
```

#### Load Tester設定

`load-tester/config.py`に追加：

```python
# 一括ユーザー管理設定
BULK_USER_MANAGEMENT = {
    'sync_enabled': True,
    'sync_interval_minutes': 30,
    'auto_login_on_sync': True,
    'max_bulk_users': 1000,
    'cleanup_on_shutdown': True,
    'user_data_file': 'data/bulk_users.json'
}

# ユーザー作成テンプレート
USER_CREATION_TEMPLATES = {
    'default': {
        'username_pattern': 'testuser_{id}@example.com',
        'password': 'TestPass123!',
        'role': 'user',
        'email_domain': 'example.com'
    },
    'admin': {
        'username_pattern': 'admin_{id}@example.com',
        'password': 'AdminPass123!',
        'role': 'admin',
        'email_domain': 'example.com'
    },
    'performance': {
        'username_pattern': 'perf_{id}@loadtest.com',
        'password': 'PerfTest123!',
        'role': 'user',
        'email_domain': 'loadtest.com'
    }
}
```

## 設定テンプレートの管理

### デフォルトテンプレートの設定

システムには以下のデフォルトテンプレートが含まれています：

#### 1. デフォルトテンプレート

```json
{
  "username_pattern": "testuser_{id}@example.com",
  "password": "TestPass123!",
  "email_domain": "example.com",
  "user_role": "user",
  "batch_size": 100,
  "custom_attributes": {}
}
```

#### 2. 管理者テンプレート

```json
{
  "username_pattern": "admin_{id}@example.com",
  "password": "AdminPass123!",
  "email_domain": "example.com",
  "user_role": "admin",
  "batch_size": 50,
  "custom_attributes": {
    "is_admin": true,
    "permissions": ["read", "write", "delete"]
  }
}
```

### カスタムテンプレートの作成

#### API経由での作成

```bash
curl -X POST http://localhost:5000/api/bulk-users/config/templates \
  -H "Content-Type: application/json" \
  -d '{
    "name": "custom_template",
    "config": {
      "username_pattern": "custom_{id}@test.com",
      "password": "CustomPass123!",
      "email_domain": "test.com",
      "batch_size": 75,
      "custom_attributes": {
        "department": "QA",
        "test_type": "performance"
      }
    }
  }'
```

#### 設定ファイル経由での作成

`data/config_templates.json`を作成：

```json
{
  "templates": {
    "qa_team": {
      "username_pattern": "qa_{id}@company.com",
      "password": "QATest123!",
      "email_domain": "company.com",
      "user_role": "tester",
      "batch_size": 50,
      "custom_attributes": {
        "department": "QA",
        "access_level": "standard"
      }
    },
    "load_test": {
      "username_pattern": "load_{id}@perf.test",
      "password": "LoadTest123!",
      "email_domain": "perf.test",
      "user_role": "user",
      "batch_size": 200,
      "custom_attributes": {
        "test_type": "load",
        "auto_cleanup": true
      }
    }
  }
}
```

## 同期設定

### Main Application ↔ Load Tester同期

#### 1. 自動同期の設定

```python
# app/config.py
SYNC_CONFIG = {
    'enabled': True,
    'interval_minutes': 30,
    'retry_attempts': 3,
    'retry_delay_seconds': 10,
    'timeout_seconds': 30
}
```

#### 2. 手動同期の実行

```bash
# 全テストユーザーを同期
curl -X POST http://localhost:5000/api/bulk-users/sync \
  -H "Content-Type: application/json" \
  -d '{
    "target": "load_tester",
    "filter_criteria": {
      "test_users_only": true
    }
  }'

# 特定のバッチのみ同期
curl -X POST http://localhost:5000/api/bulk-users/sync \
  -H "Content-Type: application/json" \
  -d '{
    "target": "load_tester",
    "filter_criteria": {
      "batch_id": "your-batch-id",
      "test_users_only": true
    }
  }'
```

#### 3. 同期状況の監視

```bash
# 同期状況確認
curl http://localhost:5000/api/bulk-users/sync/status

# 特定バッチの同期状況確認
curl "http://localhost:5000/api/bulk-users/sync/status?batch_id=your-batch-id"
```

## セキュリティ設定

### 1. 認証・認可の設定

#### Flask-Login設定

```python
# app/auth.py
from flask_login import login_required
from functools import wraps

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# 管理画面への適用
@admin_bp.route('/')
@admin_required
def admin_dashboard():
    return render_template('bulk_users/admin_dashboard.html')
```

#### API認証の設定

```python
# app/auth.py
def api_key_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key or not validate_api_key(api_key):
            return jsonify({'error': 'Invalid API key'}), 401
        return f(*args, **kwargs)
    return decorated_function
```

### 2. パスワードポリシーの設定

```python
# app/services/security_service.py
PASSWORD_POLICY = {
    'min_length': 8,
    'require_uppercase': True,
    'require_lowercase': True,
    'require_numbers': True,
    'require_special_chars': True,
    'forbidden_patterns': ['password', '123456', 'qwerty']
}
```

### 3. データ保護設定

```python
# app/config.py
DATA_PROTECTION = {
    'encrypt_passwords': True,
    'hash_algorithm': 'bcrypt',
    'salt_rounds': 12,
    'data_retention_days': 30,
    'auto_cleanup_enabled': True
}
```

## パフォーマンス設定

### 1. データベース最適化

#### インデックスの作成

```sql
-- ユーザーテーブルのインデックス
CREATE INDEX idx_users_test_batch ON users(test_batch_id);
CREATE INDEX idx_users_is_test ON users(is_test_user);
CREATE INDEX idx_users_created_by_bulk ON users(created_by_bulk);
CREATE INDEX idx_users_created_at ON users(created_at);

-- 複合インデックス
CREATE INDEX idx_users_test_batch_created ON users(test_batch_id, created_at);
```

#### 接続プール設定

```python
# app/config.py
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_size': 20,
    'pool_recycle': 3600,
    'pool_pre_ping': True,
    'max_overflow': 30
}
```

### 2. バッチ処理最適化

```python
# app/services/bulk_user_creator.py
BATCH_CONFIG = {
    'default_batch_size': 100,
    'max_batch_size': 500,
    'parallel_batches': 4,
    'commit_interval': 50,
    'memory_limit_mb': 512
}
```

### 3. 非同期処理設定

```python
# app/config.py
ASYNC_CONFIG = {
    'enabled': True,
    'worker_count': 4,
    'queue_size': 1000,
    'timeout_seconds': 300
}
```

## 監視とログ設定

### 1. ログ設定

#### ログレベルの設定

```python
# app/logging_config.py
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'detailed': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        }
    },
    'handlers': {
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/bulk_user_management.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'formatter': 'detailed'
        }
    },
    'loggers': {
        'bulk_user_management': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': False
        }
    }
}
```

#### 操作ログの設定

```python
# app/services/audit_logger.py
AUDIT_CONFIG = {
    'log_user_creation': True,
    'log_user_deletion': True,
    'log_sync_operations': True,
    'log_config_changes': True,
    'retention_days': 90
}
```

### 2. メトリクス監視

#### New Relic設定

```python
# newrelic.ini
[newrelic]
license_key = your-license-key
app_name = Bulk User Management System

# カスタムメトリクス
[newrelic:custom-metrics]
bulk_user_creation_rate = true
sync_success_rate = true
cleanup_efficiency = true
```

#### Prometheus設定

```python
# app/monitoring.py
from prometheus_client import Counter, Histogram, Gauge

# メトリクス定義
user_creation_counter = Counter('bulk_users_created_total', 'Total users created')
sync_duration_histogram = Histogram('sync_duration_seconds', 'Sync operation duration')
active_batches_gauge = Gauge('active_batches_count', 'Number of active batches')
```

## 運用設定

### 1. 定期メンテナンス

#### クリーンアップスケジュール

```bash
# crontab設定例
# 毎日午前2時に古いバッチをクリーンアップ
0 2 * * * /usr/bin/curl -X GET "http://localhost:5000/api/bulk-users/lifecycle/cleanup-candidates?age_days=7"

# 毎週日曜日午前3時に統計レポート生成
0 3 * * 0 /usr/bin/curl -X GET "http://localhost:5000/api/bulk-users/lifecycle/report"
```

#### バックアップスケジュール

```bash
# データベースバックアップ
0 1 * * * pg_dump bulk_user_db > /backup/bulk_user_db_$(date +\%Y\%m\%d).sql

# 設定ファイルバックアップ
0 1 * * * tar -czf /backup/config_$(date +\%Y\%m\%d).tar.gz /app/config/
```

### 2. アラート設定

#### エラー率監視

```python
# app/monitoring.py
ERROR_THRESHOLDS = {
    'user_creation_failure_rate': 0.05,  # 5%
    'sync_failure_rate': 0.10,           # 10%
    'cleanup_failure_rate': 0.02         # 2%
}
```

#### リソース監視

```python
# app/monitoring.py
RESOURCE_THRESHOLDS = {
    'memory_usage_percent': 80,
    'cpu_usage_percent': 70,
    'disk_usage_percent': 85,
    'database_connections': 15
}
```

## 環境別設定

### 開発環境

```env
# .env.development
DEBUG=true
DATABASE_URL=sqlite:///instance/dev.db
BULK_USER_MAX_COUNT=100
LOG_LEVEL=DEBUG
SYNC_ENABLED=false
```

### テスト環境

```env
# .env.testing
TESTING=true
DATABASE_URL=sqlite:///instance/test.db
BULK_USER_MAX_COUNT=500
LOG_LEVEL=INFO
SYNC_ENABLED=true
LOAD_TESTER_URL=http://test-load-tester:8080
```

### 本番環境

```env
# .env.production
DEBUG=false
DATABASE_URL=postgresql://user:pass@prod-db:5432/bulk_user_db
BULK_USER_MAX_COUNT=1000
LOG_LEVEL=WARNING
SYNC_ENABLED=true
LOAD_TESTER_URL=http://prod-load-tester:8080
SSL_REQUIRED=true
```

## 設定検証

### 設定の妥当性確認

```bash
# 設定検証スクリプト実行
python scripts/validate_config.py

# API経由での設定検証
curl -X POST http://localhost:5000/api/bulk-users/config/validate \
  -H "Content-Type: application/json" \
  -d @config/test_config.json
```

### 接続テスト

```bash
# データベース接続テスト
python scripts/test_db_connection.py

# Load Tester接続テスト
curl http://localhost:8080/api/health

# 同期テスト
python scripts/test_sync_connection.py
```

## 次のステップ

1. [API使用方法](bulk_user_management_api.md)を確認
2. [トラブルシューティングガイド](troubleshooting.md)を参照
3. 管理画面（`/admin/bulk-users/`）にアクセス
4. 最初のテストユーザーバッチを作成

## サポート

設定に関する問題が発生した場合：

1. ログファイルを確認（`logs/bulk_user_management.log`）
2. 設定検証スクリプトを実行
3. [トラブルシューティングガイド](troubleshooting.md)を参照
4. 必要に応じて開発チームに連絡