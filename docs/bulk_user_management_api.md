# 一括ユーザー管理システム API ドキュメント

## 概要

一括ユーザー管理システムは、負荷テスト用のユーザーを効率的に作成・管理するためのAPIを提供します。このドキュメントでは、各APIエンドポイントの使用方法を詳しく説明します。

## ベースURL

```
http://localhost:5000/api/bulk-users
```

## 認証

現在のバージョンでは、APIは認証なしでアクセス可能ですが、本番環境では適切な認証機構を実装することを推奨します。

## エンドポイント一覧

### 1. 一括ユーザー作成

#### `POST /create`

複数のテストユーザーを一括で作成します。

**リクエスト例:**
```json
{
  "count": 100,
  "config": {
    "username_pattern": "testuser_{id}@example.com",
    "password": "TestPass123!",
    "email_domain": "example.com",
    "batch_size": 50,
    "custom_attributes": {
      "role": "user",
      "department": "testing"
    }
  }
}
```

**パラメータ:**
- `count` (必須): 作成するユーザー数（1-1000）
- `config` (オプション): ユーザー作成設定
  - `username_pattern`: ユーザー名のパターン（{id}が連番に置換される）
  - `password`: 共通パスワード
  - `email_domain`: メールドメイン
  - `batch_size`: バッチサイズ（1-100）
  - `custom_attributes`: カスタム属性

**レスポンス例:**
```json
{
  "success": true,
  "batch_id": "550e8400-e29b-41d4-a716-446655440000",
  "total_requested": 100,
  "successful_count": 98,
  "failed_count": 2,
  "execution_time": 15.23,
  "created_users": [
    {
      "user_id": 1001,
      "username": "testuser_1@example.com",
      "email": "testuser_1@example.com"
    }
  ],
  "failed_users": [
    {
      "username": "testuser_50@example.com",
      "email": "testuser_50@example.com",
      "error": "Email already exists"
    }
  ]
}
```

### 2. バッチ情報取得

#### `GET /batches/{batch_id}`

指定されたバッチの情報を取得します。

**レスポンス例:**
```json
{
  "batch_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_count": 98,
  "created_at": "2024-01-15T10:30:00Z",
  "config_used": {
    "username_pattern": "testuser_{id}@example.com",
    "batch_size": 50
  }
}
```

### 3. バッチ削除

#### `DELETE /batches/{batch_id}`

指定されたバッチのすべてのテストユーザーを削除します。

**レスポンス例:**
```json
{
  "success": true,
  "batch_id": "550e8400-e29b-41d4-a716-446655440000",
  "deleted_count": 98,
  "errors": [],
  "execution_time": 2.45
}
```

### 4. ユーザーデータエクスポート

#### `GET /export`

テストユーザーのデータをJSON形式でエクスポートします。

**クエリパラメータ:**
- `batch_id` (オプション): 特定のバッチのみエクスポート
- `test_users_only` (オプション): テストユーザーのみエクスポート（デフォルト: true）

**レスポンス例:**
```json
{
  "export_timestamp": "2024-01-15T10:30:00Z",
  "source_system": "main_application",
  "total_count": 98,
  "filters": {
    "batch_id": "550e8400-e29b-41d4-a716-446655440000",
    "test_users_only": true
  },
  "users": [
    {
      "id": 1001,
      "username": "testuser_1@example.com",
      "email": "testuser_1@example.com",
      "is_test_user": true,
      "test_batch_id": "550e8400-e29b-41d4-a716-446655440000",
      "created_by_bulk": true,
      "created_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

### 5. 同期操作

#### `POST /sync`

Load Testerとの同期を実行します。

**リクエスト例:**
```json
{
  "target": "load_tester",
  "filter_criteria": {
    "batch_id": "550e8400-e29b-41d4-a716-446655440000",
    "test_users_only": true
  }
}
```

**レスポンス例:**
```json
{
  "success": true,
  "synced_count": 98,
  "failed_count": 0,
  "errors": [],
  "sync_timestamp": "2024-01-15T10:30:00Z",
  "duration": 3.21,
  "target": "load_tester",
  "filter_criteria": {
    "test_users_only": true
  }
}
```

### 6. 同期状況確認

#### `GET /sync/status`

同期の整合性を確認します。

**クエリパラメータ:**
- `batch_id` (オプション): 特定のバッチの同期状況を確認

**レスポンス例:**
```json
{
  "is_valid": true,
  "total_checked": 98,
  "inconsistencies": [],
  "validation_timestamp": "2024-01-15T10:30:00Z",
  "batch_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### 7. 統計情報取得

#### `GET /stats`

一括ユーザー管理システムの統計情報を取得します。

**レスポンス例:**
```json
{
  "total_test_users": 500,
  "total_bulk_users": 450,
  "batch_count": 5,
  "batches": [
    {
      "batch_id": "550e8400-e29b-41d4-a716-446655440000",
      "user_count": 98,
      "created_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

## 設定管理API

### 8. 設定テンプレート一覧

#### `GET /config/templates`

利用可能な設定テンプレートの一覧を取得します。

**レスポンス例:**
```json
{
  "success": true,
  "templates": [
    {
      "name": "default",
      "description": "デフォルト設定"
    },
    {
      "name": "admin",
      "description": "管理者ユーザー設定"
    }
  ]
}
```

### 9. 設定テンプレート取得

#### `GET /config/templates/{template_name}`

指定された設定テンプレートを取得します。

**レスポンス例:**
```json
{
  "success": true,
  "template_name": "default",
  "config": {
    "username_pattern": "testuser_{id}@example.com",
    "password": "TestPass123!",
    "email_domain": "example.com",
    "batch_size": 100
  },
  "validation": {
    "is_valid": true,
    "errors": [],
    "warnings": []
  },
  "description": "デフォルト設定テンプレート"
}
```

### 10. 設定テンプレート作成

#### `POST /config/templates`

新しいカスタム設定テンプレートを作成します。

**リクエスト例:**
```json
{
  "name": "custom_template",
  "config": {
    "username_pattern": "custom_{id}@test.com",
    "password": "CustomPass123!",
    "email_domain": "test.com",
    "batch_size": 50
  }
}
```

### 11. 設定検証

#### `POST /config/validate`

設定の妥当性を検証します。

**リクエスト例:**
```json
{
  "username_pattern": "testuser_{id}@example.com",
  "password": "TestPass123!",
  "email_domain": "example.com",
  "batch_size": 100
}
```

**レスポンス例:**
```json
{
  "is_valid": true,
  "errors": [],
  "warnings": [
    "パスワードが単純すぎる可能性があります"
  ],
  "config": {
    "username_pattern": "testuser_{id}@example.com",
    "password": "TestPass123!",
    "email_domain": "example.com",
    "batch_size": 100
  }
}
```

## ライフサイクル管理API

### 12. ユーザー識別

#### `POST /lifecycle/identify`

テストユーザーと本番ユーザーを識別します。

**リクエスト例:**
```json
{
  "user_ids": [1001, 1002, 1003]
}
```

**レスポンス例:**
```json
{
  "success": true,
  "identification_result": {
    "test_users": 2,
    "production_users": 1,
    "unknown_users": 0
  }
}
```

### 13. クリーンアップレポート生成

#### `GET /lifecycle/report`

クリーンアップレポートを生成します。

**クエリパラメータ:**
- `batch_id` (オプション): 特定のバッチのレポート

**レスポンス例:**
```json
{
  "success": true,
  "lifecycle_report": {
    "total_users": 1000,
    "test_users": 500,
    "active_batches": 5,
    "recommendations": [
      "古いバッチ（7日以上）のクリーンアップを推奨",
      "テストユーザーの定期的な削除を検討"
    ]
  }
}
```

### 14. 保護機能付きクリーンアップ

#### `POST /lifecycle/cleanup`

非テストユーザー削除防止機能付きでクリーンアップを実行します。

**リクエスト例:**
```json
{
  "batch_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**レスポンス例:**
```json
{
  "success": true,
  "cleanup_result": {
    "deleted_count": 98,
    "protected_count": 2,
    "errors": [],
    "execution_time": 2.45,
    "cleanup_report": {
      "batch_id": "550e8400-e29b-41d4-a716-446655440000",
      "safety_checks_passed": true
    }
  }
}
```

### 15. クリーンアップ候補取得

#### `GET /lifecycle/cleanup-candidates`

クリーンアップ候補のバッチを取得します。

**クエリパラメータ:**
- `age_days` (オプション): 古いバッチの基準日数（デフォルト: 7）

**レスポンス例:**
```json
{
  "success": true,
  "age_threshold_days": 7,
  "total_candidates": 2,
  "candidates": [
    {
      "batch_id": "old-batch-1",
      "user_count": 50,
      "created_at": "2024-01-08T10:30:00Z"
    }
  ],
  "statistics_summary": {
    "total_test_users": 500,
    "active_batches": 5,
    "protection_ratio": 0.95
  }
}
```

### 16. 同期クリーンアップ

#### `POST /lifecycle/sync-cleanup`

Main ApplicationとLoad Testerの両方からクリーンアップを実行します。

**リクエスト例:**
```json
{
  "batch_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**レスポンス例:**
```json
{
  "success": true,
  "main_application": {
    "deleted_count": 98,
    "errors": [],
    "execution_time": 2.45
  },
  "load_tester": {
    "sync_attempted": true,
    "sync_errors": []
  },
  "batch_id": "550e8400-e29b-41d4-a716-446655440000",
  "cleanup_report": {
    "safety_checks_passed": true
  },
  "sync_timestamp": "2024-01-15T10:30:00Z"
}
```

## エラーハンドリング

### HTTPステータスコード

- `200 OK`: 成功
- `201 Created`: リソース作成成功
- `400 Bad Request`: リクエストエラー
- `404 Not Found`: リソースが見つからない
- `500 Internal Server Error`: サーバーエラー

### エラーレスポンス形式

```json
{
  "error": "エラーメッセージ",
  "details": "詳細なエラー情報（オプション）"
}
```

## 使用例

### 基本的なワークフロー

1. **ユーザー作成**
```bash
curl -X POST http://localhost:5000/api/bulk-users/create \
  -H "Content-Type: application/json" \
  -d '{
    "count": 100,
    "config": {
      "username_pattern": "testuser_{id}@example.com",
      "password": "TestPass123!"
    }
  }'
```

2. **Load Testerに同期**
```bash
curl -X POST http://localhost:5000/api/bulk-users/sync \
  -H "Content-Type: application/json" \
  -d '{
    "target": "load_tester",
    "filter_criteria": {
      "test_users_only": true
    }
  }'
```

3. **統計情報確認**
```bash
curl http://localhost:5000/api/bulk-users/stats
```

4. **クリーンアップ**
```bash
curl -X DELETE http://localhost:5000/api/bulk-users/batches/{batch_id}
```

## 制限事項

- 一度に作成できるユーザー数は最大1000
- バッチサイズは最大100
- 同期処理は非同期で実行される場合があります
- クリーンアップ操作は元に戻せません

## セキュリティ考慮事項

- 本番環境では適切な認証・認可機構を実装してください
- テストユーザーのパスワードは適切にハッシュ化されます
- 非テストユーザーの削除は自動的に防止されます
- すべての操作はログに記録されます

## サポート

問題が発生した場合は、以下を確認してください：

1. APIエンドポイントが正しいか
2. リクエスト形式が正しいか
3. 必須パラメータが含まれているか
4. サーバーログでエラー詳細を確認

詳細なトラブルシューティングについては、`docs/troubleshooting.md`を参照してください。