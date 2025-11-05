# 分散サービステスト機能

Load Testerに統合された分散サービステスト機能の説明です。

## 概要

この機能は、分散トレーシングサービスに対する負荷テストを実行し、New Relicでの分散トレーシング機能を検証するために作成されました。

## 重要な注意事項

**New Relicの自動分散トレーシング機能について:**
- New Relicエージェントは自動的に分散トレーシングヘッダーを生成・送信します
- 手動でヘッダーを作成する必要はありません
- エージェント間でのトレース関連付けは自動的に行われます
- `include_trace_headers`パラメータは互換性のために残していますが、実際の動作には影響しません

## ファイル構成

### 主要ファイル

1. **`distributed_service_client.py`**
   - 分散サービスへのHTTPクライアント
   - 直接呼び出しとメインアプリ経由の呼び出しをサポート
   - レスポンス時間とエラー率の測定

2. **`distributed_test_scenarios.py`**
   - 6種類のテストシナリオを提供
   - 非同期ワーカープールによる負荷テスト実行
   - ランプアップ機能とリクエスト間隔制御

3. **`distributed_test_integration.py`**
   - Load Testerメインシステムとの統合
   - 設定管理とシナリオ実行制御

4. **`data/config.json`**
   - 分散サービステストの設定
   - テストシナリオのパラメータ設定

### テストファイル

- **`test_distributed_service_integration.py`**: 統合機能のテストコード

## 設定

### 分散サービス設定

```json
{
  "distributed_service": {
    "base_url": "http://distributed-service:5000",
    "endpoints": {
      "n-plus-one": "/performance/n-plus-one",
      "slow-query": "/performance/slow-query",
      "database-error": "/performance/database-error"
    },
    "test_scenarios": {
      "basic_distributed_tracing": {
        "concurrent_users": 1,
        "duration_minutes": 1,
        "call_type": "direct"
      }
    }
  }
}
```

### メインアプリ経由設定

```json
{
  "main_app_distributed": {
    "base_url": "http://web:5000",
    "endpoints": {
      "distributed-n-plus-one": "/distributed/n-plus-one",
      "distributed-slow-query": "/distributed/slow-query",
      "distributed-database-error": "/distributed/database-error"
    }
  }
}
```

## 使用方法

### 基本的な使用例

```python
from distributed_test_integration import DistributedTestIntegration

# 統合クラスのインスタンス作成
integration = DistributedTestIntegration()

# 利用可能なシナリオを取得
scenarios = integration.get_available_scenarios()

# 基本テストの実行
result = await integration.run_scenario("basic_distributed_tracing")

# 全シナリオの実行
all_results = await integration.run_all_scenarios()
```

### 個別クライアントの使用

```python
from distributed_service_client import DistributedServiceTestClient

async with DistributedServiceTestClient() as client:
    # 直接呼び出し
    result = await client.test_direct_call("n-plus-one", user_id=123)
    
    # メインアプリ経由呼び出し
    result = await client.test_via_main_app("slow-query", user_id=456)
```

## テストシナリオ

### 1. 基本分散トレーシングテスト
- 各エンドポイントに1回ずつリクエスト
- 分散トレーシング機能の基本動作確認

### 2. N+1クエリ負荷テスト
- N+1クエリ問題のエンドポイントに負荷をかける
- デフォルト: 10ユーザー、5分間

### 3. スロークエリ負荷テスト
- スロークエリのエンドポイントに負荷をかける
- デフォルト: 5ユーザー、3分間

### 4. データベースエラーテスト
- データベースエラーの処理とトレーシングを確認
- デフォルト: 3ユーザー、2分間

### 5. 複数ユーザー同時アクセステスト
- 複数ユーザーが同時に分散サービスにアクセス
- デフォルト: 15ユーザー、10分間

### 6. 包括的テスト
- 全エンドポイントを対象とした包括的な負荷テスト
- デフォルト: 8ユーザー、15分間

## メトリクス

各テストで以下のメトリクスが収集されます：

- **総リクエスト数**: 実行されたリクエストの総数
- **成功率**: 成功したリクエストの割合
- **平均レスポンス時間**: 全リクエストの平均レスポンス時間
- **RPS**: 1秒あたりのリクエスト数
- **エラー率**: 失敗したリクエストの割合

## ログ

テスト結果は以下のファイルに記録されます：

- `logs/distributed_service_tests.log`: 分散サービステスト専用ログ
- `logs/requests.log`: HTTPリクエストの詳細ログ

## New Relic連携

### 自動分散トレーシング

New Relicエージェントが以下を自動的に処理します：

1. **分散トレーシングヘッダーの生成**: リクエスト間のトレース関連付け用ヘッダー
2. **ヘッダーの送信**: HTTPリクエストに自動的にヘッダーを追加
3. **トレースの関連付け**: 複数サービス間でのトレース連携
4. **Custom Attributeの設定**: userIdなどのカスタム属性の自動設定

### 監視項目

New Relicで以下の項目を監視できます：

- 分散トレーシングビュー
- レスポンス時間メトリクス
- エラー率とエラー詳細
- データベースクエリのパフォーマンス
- Custom Attributeによるユーザー別分析

## トラブルシューティング

### よくある問題

1. **接続エラー**
   - 分散サービスが起動していることを確認
   - ネットワーク設定とポート番号を確認

2. **タイムアウトエラー**
   - `timeout_seconds`設定を調整
   - スロークエリテストでは長めのタイムアウトを設定

3. **New Relicでトレースが表示されない**
   - New Relicエージェントが正しく設定されていることを確認
   - `distributed_tracing.enabled = true`が設定されていることを確認

### デバッグ

ログレベルをDEBUGに設定して詳細な情報を確認：

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 今後の拡張

- New Relic API連携による自動検証機能
- より詳細なパフォーマンスメトリクス
- カスタムテストシナリオの動的作成
- リアルタイムダッシュボード機能