# 一括ユーザー管理システム トラブルシューティングガイド

## 概要

このガイドでは、一括ユーザー管理システムで発生する可能性のある問題と、その解決方法を説明します。

## 一般的な問題と解決方法

### 1. ユーザー作成関連の問題

#### 問題: ユーザー作成が失敗する

**症状:**
- APIが500エラーを返す
- 一部のユーザーのみ作成される
- 作成処理が途中で停止する

**原因と解決方法:**

##### 原因1: データベース制約違反
```bash
# エラーログ確認
tail -f logs/bulk_user_management.log | grep "UNIQUE constraint"

# 解決方法: 重複チェック
curl -X GET "http://localhost:5000/api/bulk-users/stats"
```

##### 原因2: メモリ不足
```bash
# メモリ使用量確認
free -h
ps aux | grep python | head -5

# 解決方法: バッチサイズを小さくする
curl -X POST http://localhost:5000/api/bulk-users/create \
  -H "Content-Type: application/json" \
  -d '{
    "count": 100,
    "config": {
      "batch_size": 25
    }
  }'
```

##### 原因3: データベース接続制限
```bash
# 接続数確認（PostgreSQLの場合）
psql -c "SELECT count(*) FROM pg_stat_activity;"

# 解決方法: 接続プール設定調整
# app/config.py
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_size': 10,
    'max_overflow': 20
}
```

#### 問題: ユーザー名パターンが正しく動作しない

**症状:**
- 期待したユーザー名が生成されない
- {id}が置換されない

**解決方法:**
```bash
# パターン検証
curl -X POST http://localhost:5000/api/bulk-users/config/validate \
  -H "Content-Type: application/json" \
  -d '{
    "username_pattern": "testuser_{id}@example.com"
  }'

# 正しいパターン例
{
  "username_pattern": "user_{id}@domain.com",  # ✓ 正しい
  "username_pattern": "user_${id}@domain.com", # ✗ 間違い
  "username_pattern": "user_{index}@domain.com" # ✗ 間違い
}
```

### 2. 同期関連の問題

#### 問題: Load Testerとの同期が失敗する

**症状:**
- 同期APIが失敗する
- データの不整合が発生する
- 同期処理がタイムアウトする

**診断手順:**

##### 1. 接続確認
```bash
# Load Tester接続テスト
curl -v http://localhost:8080/api/health

# ネットワーク確認
ping load-tester-host
telnet load-tester-host 8080
```

##### 2. 同期状況確認
```bash
# 同期状況チェック
curl http://localhost:5000/api/bulk-users/sync/status

# 詳細ログ確認
tail -f logs/bulk_user_management.log | grep "sync"
```

##### 3. 手動同期テスト
```bash
# 小さなデータセットで同期テスト
curl -X POST http://localhost:5000/api/bulk-users/sync \
  -H "Content-Type: application/json" \
  -d '{
    "target": "load_tester",
    "filter_criteria": {
      "batch_id": "test-batch-id",
      "test_users_only": true
    }
  }'
```

**解決方法:**

##### タイムアウト問題
```python
# app/config.py
SYNC_CONFIG = {
    'timeout_seconds': 60,  # デフォルト30から増加
    'retry_attempts': 5,    # デフォルト3から増加
    'retry_delay_seconds': 15
}
```

##### データ形式問題
```bash
# エクスポートデータ確認
curl http://localhost:5000/api/bulk-users/export?batch_id=test-batch

# Load Tester側のログ確認
tail -f load-tester/logs/sync.log
```

#### 問題: 同期データの不整合

**症状:**
- Main ApplicationとLoad Testerでユーザー数が異なる
- 一部のユーザーが同期されない

**診断と解決:**

```bash
# 1. 統計情報比較
curl http://localhost:5000/api/bulk-users/stats
curl http://localhost:8080/api/users/stats

# 2. 整合性チェック
curl http://localhost:5000/api/bulk-users/sync/status

# 3. 強制再同期
curl -X POST http://localhost:5000/api/bulk-users/sync \
  -H "Content-Type: application/json" \
  -d '{
    "target": "load_tester",
    "filter_criteria": {
      "test_users_only": true
    }
  }'
```

### 3. クリーンアップ関連の問題

#### 問題: クリーンアップが実行されない

**症状:**
- 削除APIが成功するが実際に削除されない
- 保護機能が過剰に動作する

**診断手順:**

```bash
# 1. バッチ存在確認
curl http://localhost:5000/api/bulk-users/batches/{batch_id}

# 2. ユーザー識別確認
curl -X POST http://localhost:5000/api/bulk-users/lifecycle/identify \
  -H "Content-Type: application/json" \
  -d '{}'

# 3. クリーンアップ候補確認
curl http://localhost:5000/api/bulk-users/lifecycle/cleanup-candidates
```

**解決方法:**

##### 保護機能の調整
```python
# app/services/bulk_user_creator.py
PROTECTION_CONFIG = {
    'strict_mode': False,  # 厳格モードを無効化
    'allow_partial_cleanup': True,
    'confirmation_required': False
}
```

##### 強制クリーンアップ
```bash
# 保護機能付きクリーンアップ
curl -X POST http://localhost:5000/api/bulk-users/lifecycle/cleanup \
  -H "Content-Type: application/json" \
  -d '{
    "batch_id": "your-batch-id"
  }'
```

#### 問題: 本番ユーザーが誤って削除される危険性

**予防策:**

```bash
# 1. 削除前の確認
curl -X POST http://localhost:5000/api/bulk-users/lifecycle/identify

# 2. テストユーザーのマーキング確認
curl http://localhost:5000/api/bulk-users/export | jq '.users[] | select(.is_test_user == false)'

# 3. バックアップ作成
pg_dump -t users bulk_user_db > backup_before_cleanup.sql
```

### 4. パフォーマンス関連の問題

#### 問題: 大量ユーザー作成時の性能低下

**症状:**
- 作成処理が非常に遅い
- メモリ使用量が急増する
- データベースがロックされる

**解決方法:**

##### バッチサイズの最適化
```bash
# 小さなバッチサイズでテスト
curl -X POST http://localhost:5000/api/bulk-users/create \
  -H "Content-Type: application/json" \
  -d '{
    "count": 1000,
    "config": {
      "batch_size": 50  # デフォルト100から削減
    }
  }'
```

##### データベース最適化
```sql
-- インデックス確認
SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'users';

-- 統計情報更新
ANALYZE users;

-- 不要なデータの削除
DELETE FROM users WHERE is_test_user = true AND created_at < NOW() - INTERVAL '30 days';
```

##### メモリ使用量監視
```bash
# プロセス監視
watch -n 1 'ps aux | grep python | head -5'

# メモリ使用量確認
free -h && echo "---" && ps -o pid,ppid,cmd,%mem,%cpu --sort=-%mem | head
```

#### 問題: 同期処理の性能問題

**解決方法:**

##### 並列処理の有効化
```python
# app/config.py
SYNC_CONFIG = {
    'parallel_enabled': True,
    'worker_count': 4,
    'chunk_size': 100
}
```

##### 差分同期の実装
```bash
# 最後の同期以降の変更のみ同期
curl -X POST http://localhost:5000/api/bulk-users/sync \
  -H "Content-Type: application/json" \
  -d '{
    "target": "load_tester",
    "filter_criteria": {
      "modified_since": "2024-01-15T10:00:00Z"
    }
  }'
```

### 5. 設定関連の問題

#### 問題: 設定テンプレートが読み込まれない

**症状:**
- テンプレート一覧が空
- カスタムテンプレートが保存されない

**解決方法:**

```bash
# 1. 設定ファイル確認
ls -la data/config_templates.json
cat data/config_templates.json | jq '.'

# 2. 権限確認
chmod 644 data/config_templates.json
chown app:app data/config_templates.json

# 3. テンプレート再読み込み
curl -X GET http://localhost:5000/api/bulk-users/config/templates
```

#### 問題: 設定検証エラー

**症状:**
- 設定が無効と判定される
- 警告メッセージが多数表示される

**解決方法:**

```bash
# 設定検証の詳細確認
curl -X POST http://localhost:5000/api/bulk-users/config/validate \
  -H "Content-Type: application/json" \
  -d '{
    "username_pattern": "test_{id}@example.com",
    "password": "TestPass123!",
    "email_domain": "example.com",
    "batch_size": 100
  }' | jq '.'

# 最小設定での検証
curl -X POST http://localhost:5000/api/bulk-users/config/validate \
  -H "Content-Type: application/json" \
  -d '{
    "username_pattern": "user_{id}@test.com"
  }'
```

### 6. 認証・認可関連の問題

#### 問題: 管理画面にアクセスできない

**症状:**
- 403 Forbiddenエラー
- ログイン後もアクセス拒否される

**解決方法:**

```bash
# 1. ユーザー権限確認
curl -H "Authorization: Bearer your-token" \
  http://localhost:5000/api/user/profile

# 2. 管理者権限付与（データベース直接操作）
psql bulk_user_db -c "UPDATE users SET is_admin = true WHERE username = 'your-username';"

# 3. セッション確認
curl -b cookies.txt http://localhost:5000/admin/bulk-users/
```

#### 問題: API認証エラー

**解決方法:**

```bash
# APIキー確認
curl -H "X-API-Key: your-api-key" \
  http://localhost:5000/api/bulk-users/stats

# 認証なしでのテスト（開発環境のみ）
export DISABLE_AUTH=true
```

## ログ分析

### 重要なログパターン

#### エラーログの確認
```bash
# 一般的なエラー
tail -f logs/bulk_user_management.log | grep "ERROR"

# 特定の操作のエラー
tail -f logs/bulk_user_management.log | grep "bulk_user_creation"

# 同期関連のエラー
tail -f logs/bulk_user_management.log | grep "sync"
```

#### パフォーマンスログの確認
```bash
# 実行時間の長い操作
tail -f logs/bulk_user_management.log | grep "execution_time" | awk '$NF > 10'

# メモリ使用量警告
tail -f logs/bulk_user_management.log | grep "memory"
```

### ログレベルの調整

```python
# 一時的なデバッグモード
import logging
logging.getLogger('bulk_user_management').setLevel(logging.DEBUG)

# 設定ファイルでの調整
LOG_LEVEL=DEBUG
```

## 診断スクリプト

### システム健全性チェック

```bash
#!/bin/bash
# scripts/health_check.sh

echo "=== 一括ユーザー管理システム健全性チェック ==="

# 1. データベース接続確認
echo "1. データベース接続確認..."
python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.engine.execute('SELECT 1')" && echo "OK" || echo "NG"

# 2. API応答確認
echo "2. API応答確認..."
curl -s http://localhost:5000/api/bulk-users/stats > /dev/null && echo "OK" || echo "NG"

# 3. Load Tester接続確認
echo "3. Load Tester接続確認..."
curl -s http://localhost:8080/api/health > /dev/null && echo "OK" || echo "NG"

# 4. ディスク容量確認
echo "4. ディスク容量確認..."
df -h | grep -E "(80%|90%|100%)" && echo "警告: ディスク容量不足" || echo "OK"

# 5. メモリ使用量確認
echo "5. メモリ使用量確認..."
free | awk 'NR==2{printf "メモリ使用率: %.2f%%\n", $3*100/$2}'
```

### 設定検証スクリプト

```python
#!/usr/bin/env python
# scripts/validate_config.py

import json
import requests
import sys

def validate_config():
    """設定の妥当性を検証"""
    
    # 基本設定テスト
    test_config = {
        "username_pattern": "test_{id}@example.com",
        "password": "TestPass123!",
        "email_domain": "example.com",
        "batch_size": 100
    }
    
    try:
        response = requests.post(
            'http://localhost:5000/api/bulk-users/config/validate',
            json=test_config
        )
        
        if response.status_code == 200:
            result = response.json()
            if result['is_valid']:
                print("✓ 設定は有効です")
                return True
            else:
                print("✗ 設定エラー:")
                for error in result['errors']:
                    print(f"  - {error}")
                return False
        else:
            print(f"✗ API エラー: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"✗ 接続エラー: {e}")
        return False

if __name__ == "__main__":
    if validate_config():
        sys.exit(0)
    else:
        sys.exit(1)
```

## 緊急時の対応

### システム停止手順

```bash
# 1. 進行中の処理確認
curl http://localhost:5000/api/bulk-users/stats

# 2. 新規リクエスト停止（ロードバランサー設定）
# nginx.conf: upstream に down フラグ追加

# 3. 進行中の処理完了待ち
while [ $(curl -s http://localhost:5000/api/bulk-users/stats | jq '.active_operations') -gt 0 ]; do
  echo "処理完了待ち..."
  sleep 10
done

# 4. アプリケーション停止
pkill -f "python.*app"
```

### データ復旧手順

```bash
# 1. バックアップからの復旧
pg_restore -d bulk_user_db backup_file.sql

# 2. 整合性チェック
curl http://localhost:5000/api/bulk-users/sync/status

# 3. 必要に応じて再同期
curl -X POST http://localhost:5000/api/bulk-users/sync \
  -H "Content-Type: application/json" \
  -d '{"target": "load_tester", "filter_criteria": {"test_users_only": true}}'
```

## 予防保守

### 定期チェック項目

1. **日次チェック**
   - ログファイルサイズ
   - エラー率
   - 同期状況

2. **週次チェック**
   - データベース統計情報更新
   - 古いバッチのクリーンアップ
   - パフォーマンスメトリクス確認

3. **月次チェック**
   - 設定の見直し
   - セキュリティ更新
   - 容量計画の確認

### 監視アラート設定

```python
# app/monitoring.py
ALERT_THRESHOLDS = {
    'user_creation_failure_rate': 0.05,
    'sync_failure_rate': 0.10,
    'response_time_p95': 5.0,  # 秒
    'memory_usage_percent': 80,
    'disk_usage_percent': 85
}
```

## サポート連絡先

問題が解決しない場合：

1. **ログファイル**を添付
2. **エラーメッセージ**の詳細を記録
3. **再現手順**を明確にする
4. **環境情報**（OS、Python版、データベース版）を提供

**緊急時連絡先:** [開発チーム連絡先]
**ドキュメント更新:** [ドキュメント管理者連絡先]