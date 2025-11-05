# Design Document

## Overview

New Relicの分散トレーシング機能を効果的に活用するため、メインのFlaskアプリケーションとは独立したコンテナで動作するWebサービス（Distributed Service）を作成する。このサービスは、HTTP経由でデータベースアクセス処理を同期実行し、userIdをCustom AttributeとしてNew Relicに送信することで、分散システム全体の可視性を向上させる。

## Architecture

### System Components

```mermaid
graph TB
    subgraph "Main Container"
        MA[Main Flask App]
        NR1[New Relic Agent]
    end
    
    subgraph "Distributed Service Container"
        DS[Distributed Service]
        NR2[New Relic Agent]
    end
    
    subgraph "Database Container"
        DB[(PostgreSQL)]
    end
    
    subgraph "New Relic Platform"
        APM[APM Dashboard]
        DT[Distributed Tracing]
        CA[Custom Attributes]
    end
    
    MA -->|HTTP Request with userId| DS
    DS -->|Database Queries| DB
    DS -->|HTTP Response| MA
    
    NR1 -->|Trace Data + Custom Attributes| APM
    NR2 -->|Trace Data + Custom Attributes| DT
    
    NR1 -.->|Distributed Tracing Headers| NR2
```

### Container Architecture

1. **Main Application Container** (既存)
   - 既存のFlaskアプリケーション
   - New Relicエージェント統合済み
   - 分散サービスへのHTTPクライアント機能を追加

2. **Distributed Service Container** (新規作成)
   - 独立したFlaskアプリケーション
   - New Relicエージェント統合
   - データベース直接アクセス
   - パフォーマンス問題のあるエンドポイント

3. **PostgreSQL Container** (既存)
   - 両方のサービスからアクセス可能
   - New Relic PostgreSQL統合

## Components and Interfaces

### 1. Distributed Service Application

**Technology Stack:**
- Flask (軽量なWebフレームワーク)
- SQLAlchemy (データベースORM)
- New Relic Python Agent
- PostgreSQL Driver (psycopg2)

**Core Components:**

#### 1.1 Flask Application (`distributed_service/app.py`)
```python
# 基本的なFlaskアプリケーション構造
# New Relicエージェントの初期化
# データベース接続設定
# ルート登録
```

#### 1.2 Database Models (`distributed_service/models.py`)
```python
# 既存のUser, Product, Order, OrderItemモデルと同等
# 分散サービス専用のモデル（必要に応じて）
```

#### 1.3 Performance Issue Routes (`distributed_service/routes/performance.py`)
```python
# N+1クエリ問題のエンドポイント
# スロークエリのエンドポイント
# データベースエラーのエンドポイント
# 各エンドポイントでuserIdのCustom Attribute設定
```

#### 1.4 New Relic Integration (`distributed_service/newrelic_utils.py`)
```python
# Custom Attribute設定ユーティリティ
# 分散トレーシングヘッダー処理
# エラー報告機能
```

### 2. Main Application Integration

#### 2.1 HTTP Client Service (`app/services/distributed_client.py`)
```python
# 分散サービスへのHTTP呼び出し
# New Relic分散トレーシングヘッダーの送信
# レスポンス処理とエラーハンドリング
```

#### 2.2 Distributed Routes (`app/routes/distributed.py`)
```python
# 分散サービス呼び出しのエンドポイント
# ユーザー認証とuserIdの取得
# 分散サービスへのプロキシ機能
```

#### 2.3 Web UI Templates (`app/templates/distributed/`)
```html
# 分散トレーシングデモページ (index.html)
# N+1クエリ、スロークエリ、エラー発生の実行ボタン
# 実行結果とレスポンス時間の表示
# 既存のperformanceデモページと同様のスタイル
```

### 3. Docker Configuration

#### 3.1 Distributed Service Dockerfile
```dockerfile
# Python 3.9ベースイメージ
# 必要なパッケージのインストール
# New Relic設定ファイルのコピー
# アプリケーションコードのコピー
# ポート5002の公開
```

#### 3.2 Docker Compose更新
```yaml
# distributed-serviceサービスの追加
# ネットワーク設定
# 環境変数設定
# 依存関係設定
```

## Data Models

### Database Schema
既存のデータベーススキーマを使用：
- `users` テーブル
- `products` テーブル
- `orders` テーブル
- `order_items` テーブル

### API Request/Response Models

#### HTTP Request Format
```json
{
  "user_id": 123,
  "operation": "n_plus_one|slow_query|database_error",
  "parameters": {
    "limit": 10,
    "category": "Electronics"
  }
}
```

#### HTTP Response Format
```json
{
  "status": "success|error",
  "data": {
    "results": [...],
    "execution_time": 2.5,
    "query_count": 15
  },
  "user_id": 123,
  "trace_id": "abc123def456"
}
```

## Error Handling

### 1. Database Connection Errors
- 接続失敗時の自動リトライ
- New Relicへのエラー報告
- 適切なHTTPステータスコード返却

### 2. Query Execution Errors
- SQLエラーのキャッチと処理
- userIdを含むCustom Attributeでエラー報告
- 詳細なエラーログ出力

### 3. HTTP Communication Errors
- タイムアウト処理
- 接続エラーのハンドリング
- フォールバック機能

### 4. New Relic Integration Errors
- エージェント初期化失敗の処理
- Custom Attribute設定エラーの処理
- 分散トレーシングヘッダー処理エラー

## Testing Strategy

### 1. Unit Tests
- 各エンドポイントの基本機能テスト
- New Relic Custom Attribute設定のテスト
- データベースクエリのテスト

### 2. Integration Tests
- メインアプリケーションから分散サービスへの呼び出しテスト
- 分散トレーシングの連携テスト
- エラーハンドリングのテスト

### 3. Performance Tests
- N+1クエリ問題の検証
- スロークエリの実行時間測定
- New Relicでの監視データ確認

### 4. Load Testing with Load Tester Integration
- 分散サービスエンドポイントの負荷テスト
- 複数ユーザーでの同時アクセステスト
- メインアプリケーション経由での分散呼び出し負荷テスト
- パフォーマンス問題エンドポイントの個別負荷テスト

### 5. Automated Test Scenarios
- 分散トレーシングヘッダー伝播の自動検証
- userIdのCustom Attribute設定の自動確認
- New Relic分散トレーシング表示の自動検証
- エラーシナリオの自動実行と検証

### 6. New Relic Monitoring Tests
- Custom Attributeの表示確認
- 分散トレーシングの可視化確認
- エラー追跡機能の確認

## Implementation Details

### 1. New Relic Configuration

#### Distributed Service New Relic設定
```ini
# distributed_service/newrelic.ini
[newrelic]
app_name = Flask-EC-Distributed-Service
distributed_tracing.enabled = true
# その他の設定は既存のnewrelic.iniと同様
```

#### Custom Attribute設定
```python
import newrelic.agent

@newrelic.agent.function_trace()
def process_with_user_id(user_id, operation):
    # userIdをCustom Attributeとして設定
    newrelic.agent.add_custom_attribute('user_id', user_id)
    newrelic.agent.add_custom_attribute('operation_type', operation)
    newrelic.agent.add_custom_attribute('service_name', 'distributed-service')
```

### 2. Performance Issue Implementations

#### N+1クエリ問題
```python
@bp.route('/n-plus-one')
def n_plus_one_with_user_id():
    user_id = request.json.get('user_id')
    newrelic.agent.add_custom_attribute('user_id', user_id)
    
    # N+1クエリの実装（既存のperformance_issues.pyを参考）
    products = Product.query.limit(20).all()
    for product in products:
        order_count = OrderItem.query.filter_by(product_id=product.id).count()
```

#### スロークエリ
```python
@bp.route('/slow-query')
def slow_query_with_user_id():
    user_id = request.json.get('user_id')
    newrelic.agent.add_custom_attribute('user_id', user_id)
    
    # pg_sleepを使った意図的な遅延
    sleep_duration = random.uniform(3.0, 5.0)
    db.session.execute(text(f"SELECT pg_sleep({sleep_duration})"))
```

### 3. HTTP Client Implementation

#### メインアプリケーション側
```python
import requests
import newrelic.agent

class DistributedServiceClient:
    def __init__(self, base_url):
        self.base_url = base_url
    
    @newrelic.agent.function_trace()
    def call_performance_endpoint(self, user_id, operation):
        # 分散トレーシングヘッダーの生成
        headers = {}
        newrelic.agent.insert_distributed_trace_headers(headers)
        
        # userIdをCustom Attributeとして設定
        newrelic.agent.add_custom_attribute('user_id', user_id)
        newrelic.agent.add_custom_attribute('distributed_call', True)
        
        response = requests.post(
            f"{self.base_url}/{operation}",
            json={"user_id": user_id},
            headers=headers
        )
        return response.json()
```

### 4. Docker Configuration Details

#### docker-compose.yml更新
```yaml
distributed-service:
  build: ./distributed-service
  container_name: flask-ec-distributed-service
  environment:
    - DATABASE_URL=postgresql://postgres:postgres@postgres:5432/ecdb
    - NEW_RELIC_LICENSE_KEY=${NEW_RELIC_LICENSE_KEY}
    - NEW_RELIC_APP_NAME=Flask-EC-Distributed-Service
    - NEW_RELIC_ENVIRONMENT=development
  ports:
    - "5002:5000"
  depends_on:
    postgres:
      condition: service_healthy
  networks:
    - flask-ec-network
```

## Security Considerations

### 1. Authentication
- 分散サービスへのアクセス制御
- APIキーまたはJWTトークンによる認証

### 2. Network Security
- 内部ネットワーク通信の暗号化
- ファイアウォール設定

### 3. Data Protection
- userIdの適切な処理
- 機密情報のログ出力防止

## Monitoring and Observability

### 1. New Relic Dashboards
- 分散トレーシングビュー
- Custom Attributeによるユーザー別分析
- パフォーマンス問題の可視化

### 2. Logging Strategy
- 構造化ログ出力
- userIdを含むログエントリ
- エラーログの詳細化

### 3. Metrics Collection
- レスポンス時間メトリクス
- エラー率メトリクス
- データベースクエリメトリクス
## Loa
d Tester Integration Design

### 1. Load Tester Components

#### 1.1 Distributed Service Test Client (`load-tester/distributed_service_client.py`)
```python
# 分散サービスへの直接呼び出し機能
# メインアプリケーション経由での分散サービス呼び出し
# 各パフォーマンス問題エンドポイントの個別テスト
# レスポンス時間とエラー率の測定
# New Relic分散トレーシングヘッダーの処理

class DistributedServiceTestClient:
    def __init__(self, config):
        self.distributed_url = config['distributed_service']['base_url']
        self.main_app_url = config['main_app_distributed']['base_url']
    
    def test_direct_call(self, endpoint, user_id):
        # 分散サービスへの直接呼び出し
        
    def test_via_main_app(self, endpoint, user_id):
        # メインアプリケーション経由での呼び出し
```

#### 1.2 Test Scenario Definitions (`load-tester/test_distributed_scenarios.py`)
```python
# 基本的な分散トレーシングテストシナリオ
# N+1クエリ問題の負荷テストシナリオ
# スロークエリの負荷テストシナリオ
# データベースエラーの負荷テストシナリオ
# 複数ユーザー同時アクセスシナリオ

class DistributedTestScenarios:
    def basic_distributed_tracing_test(self):
        # 基本的な分散トレーシング機能のテスト
        
    def n_plus_one_load_test(self, concurrent_users=10):
        # N+1クエリ問題の負荷テスト
        
    def slow_query_load_test(self, concurrent_users=5):
        # スロークエリの負荷テスト
        
    def error_handling_test(self):
        # エラーハンドリングのテスト
```

#### 1.3 New Relic Verification (`load-tester/newrelic_verification.py`)
```python
# New Relic APIを使った分散トレーシング確認
# Custom Attributeの自動検証
# エラー追跡データの確認
# パフォーマンスメトリクスの検証

class NewRelicVerification:
    def verify_distributed_trace(self, trace_id):
        # 分散トレーシングの確認
        
    def verify_custom_attributes(self, user_id):
        # Custom Attributeの確認
        
    def verify_performance_metrics(self, endpoint):
        # パフォーマンスメトリクスの確認
```

### 2. Load Tester Configuration Updates

#### 2.1 Configuration File Updates (`load-tester/data/config.json`)
```json
{
  "distributed_service": {
    "base_url": "http://localhost:5002",
    "endpoints": {
      "n_plus_one": "/performance/n-plus-one",
      "slow_query": "/performance/slow-query",
      "database_error": "/performance/database-error"
    },
    "test_scenarios": {
      "basic_load": {
        "concurrent_users": 10,
        "duration": 60,
        "ramp_up": 10
      },
      "stress_test": {
        "concurrent_users": 50,
        "duration": 120,
        "ramp_up": 30
      }
    }
  },
  "main_app_distributed": {
    "base_url": "http://localhost:5000",
    "endpoints": {
      "distributed_n_plus_one": "/distributed/n-plus-one",
      "distributed_slow_query": "/distributed/slow-query",
      "distributed_database_error": "/distributed/database-error"
    }
  },
  "newrelic_verification": {
    "api_key": "${NEW_RELIC_API_KEY}",
    "account_id": "${NEW_RELIC_ACCOUNT_ID}",
    "app_names": [
      "Flask-EC-Main-App",
      "Flask-EC-Distributed-Service"
    ]
  }
}
```

### 3. Test Execution Flow

#### 3.1 Automated Test Pipeline
```mermaid
graph TD
    A[Start Load Test] --> B[Initialize Test Environment]
    B --> C[Execute Basic Distributed Tracing Test]
    C --> D[Execute N+1 Query Load Test]
    D --> E[Execute Slow Query Load Test]
    E --> F[Execute Error Handling Test]
    F --> G[Collect Performance Metrics]
    G --> H[Verify New Relic Data]
    H --> I[Generate Test Report]
    I --> J[End]
```

#### 3.2 Test Metrics Collection
- レスポンス時間の測定
- エラー率の計算
- スループットの測定
- New Relic分散トレーシングデータの検証
- Custom Attributeの確認
- データベースパフォーマンスメトリクス

### 4. Integration Points

#### 4.1 Load Tester Dashboard Updates
- 分散サービステスト結果の表示
- 分散トレーシングメトリクスの可視化
- New Relic連携状況の表示
- エラー率とレスポンス時間のグラフ

#### 4.2 Continuous Integration
- 自動化されたテストスイートの実行
- New Relic監視データの自動検証
- パフォーマンス回帰テストの実行
- テスト結果のレポート生成