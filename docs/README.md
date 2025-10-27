# 一括ユーザー管理システム

## 概要

一括ユーザー管理システムは、負荷テスト用のユーザーを効率的に作成・管理し、Main ApplicationとLoad Tester間でユーザーデータを同期するためのシステムです。

## 主な機能

### 1. 一括ユーザー作成
- 最大1000ユーザーの一括作成
- カスタマイズ可能なユーザー名パターン
- バッチ単位での管理
- 部分的失敗時の継続処理

### 2. ユーザー同期
- Main Application ↔ Load Tester間の自動同期
- JSON形式でのデータ交換
- 同期整合性の検証
- エラー時の自動リトライ

### 3. ライフサイクル管理
- テストユーザーと本番ユーザーの識別
- バッチ単位での安全な削除
- 非テストユーザー削除防止機能
- クリーンアップレポート生成

### 4. 設定管理
- 設定テンプレートシステム
- カスタム設定の作成・管理
- 設定の妥当性検証
- テンプレートのインポート・エクスポート

### 5. 管理UI
- Web管理画面
- 同期状況ダッシュボード
- リアルタイム監視
- 操作ログ表示

## システム構成

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Main           │    │  User Sync      │    │  Load Tester    │
│  Application    │◄──►│  Service        │◄──►│                 │
│                 │    │                 │    │                 │
│ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │Bulk User    │ │    │ │Export/Import│ │    │ │User Session │ │
│ │Creator      │ │    │ │Manager      │ │    │ │Manager      │ │
│ └─────────────┘ │    │ └─────────────┘ │    │ └─────────────┘ │
│                 │    │                 │    │                 │
│ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │Config       │ │    │ │Validation   │ │    │ │Config       │ │
│ │Manager      │ │    │ │Service      │ │    │ │Manager      │ │
│ └─────────────┘ │    │ └─────────────┘ │    │ └─────────────┘ │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## クイックスタート

### 1. 環境設定

```bash
# 依存関係インストール
pip install -r requirements.txt

# 環境変数設定
cp .env.example .env
# .envファイルを編集

# データベースマイグレーション
flask db upgrade
```

### 2. 基本的な使用方法

#### ユーザー作成
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

#### 同期実行
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

#### 管理画面アクセス
```
http://localhost:5000/admin/bulk-users/
```

### 3. 設定例

#### デフォルト設定テンプレート
```json
{
  "username_pattern": "testuser_{id}@example.com",
  "password": "TestPass123!",
  "email_domain": "example.com",
  "batch_size": 100,
  "custom_attributes": {}
}
```

#### Load Tester設定
```python
BULK_USER_MANAGEMENT = {
    'sync_enabled': True,
    'sync_interval_minutes': 30,
    'auto_login_on_sync': True,
    'max_bulk_users': 1000,
    'cleanup_on_shutdown': True
}
```

## ドキュメント

### API仕様
- [API使用方法](bulk_user_management_api.md) - 全APIエンドポイントの詳細仕様

### 設定・運用
- [設定ガイド](bulk_user_management_setup_guide.md) - 初期設定から運用まで
- [トラブルシューティング](troubleshooting.md) - 問題解決ガイド

### 管理画面
- **メイン管理画面**: `/admin/bulk-users/` - 全機能へのアクセス
- **同期ダッシュボード**: `/admin/bulk-users/sync` - 同期状況の監視

## 主要なAPIエンドポイント

### ユーザー管理
- `POST /api/bulk-users/create` - 一括ユーザー作成
- `GET /api/bulk-users/batches/{batch_id}` - バッチ情報取得
- `DELETE /api/bulk-users/batches/{batch_id}` - バッチ削除
- `GET /api/bulk-users/stats` - 統計情報取得

### 同期管理
- `POST /api/bulk-users/sync` - 同期実行
- `GET /api/bulk-users/sync/status` - 同期状況確認
- `GET /api/bulk-users/export` - ユーザーデータエクスポート

### 設定管理
- `GET /api/bulk-users/config/templates` - テンプレート一覧
- `POST /api/bulk-users/config/templates` - テンプレート作成
- `POST /api/bulk-users/config/validate` - 設定検証

### ライフサイクル管理
- `POST /api/bulk-users/lifecycle/cleanup` - 保護機能付きクリーンアップ
- `GET /api/bulk-users/lifecycle/cleanup-candidates` - クリーンアップ候補取得
- `POST /api/bulk-users/lifecycle/identify` - ユーザー識別

## セキュリティ機能

### データ保護
- テストユーザーのパスワードハッシュ化
- 非テストユーザー削除防止機能
- バッチ単位での安全な削除

### アクセス制御
- 管理画面への認証・認可
- API操作のログ記録
- テストユーザーと本番ユーザーの分離

### 監査機能
- 全操作のログ記録
- クリーンアップレポート生成
- 同期整合性の検証

## パフォーマンス特性

### スケーラビリティ
- 最大1000ユーザーの一括作成
- バッチ処理による効率的な作成
- 並列処理による高速化

### 最適化機能
- データベース一括挿入
- 非同期処理
- メモリ効率的なデータ処理

### 監視機能
- リアルタイム進捗表示
- パフォーマンスメトリクス
- リソース使用量監視

## 要件対応状況

### 要件1: 一括ユーザー作成機能
- ✅ 最大1000ユーザーの一括作成
- ✅ ユニークな認証情報生成
- ✅ 構造化フォーマットでの保存
- ✅ 部分的失敗時の継続処理
- ✅ 30秒以内での100ユーザー作成

### 要件2: ユーザーデータ同期機能
- ✅ JSON形式でのエクスポート
- ✅ Load Testerへのインポート
- ✅ 10秒以内での同期更新
- ✅ 認証情報の検証
- ✅ 失敗時のデータ維持とログ記録

### 要件3: ライフサイクル管理機能
- ✅ バッチ単位でのテストユーザー削除
- ✅ テストユーザーの識別マーキング
- ✅ 両システムからの削除
- ✅ クリーンアップレポート生成
- ✅ 非テストユーザー削除防止

### 要件4: 設定管理機能
- ✅ ユーザー名パターンとメールドメイン設定
- ✅ 異なるユーザーロール割り当て
- ✅ カスタムユーザー属性適用
- ✅ 設定パラメータ検証
- ✅ テンプレート提供

## 制限事項

### 技術的制限
- 一度に作成できるユーザー数: 最大1000
- バッチサイズ: 最大500
- 同期タイムアウト: 60秒
- 設定テンプレート数: 最大100

### 運用上の制限
- テストユーザーの自動削除: 30日後
- 同期履歴保持期間: 90日
- ログファイル保持期間: 30日
- バックアップ保持期間: 7日

## トラブルシューティング

### よくある問題
1. **ユーザー作成失敗** → [トラブルシューティングガイド](troubleshooting.md#ユーザー作成関連の問題)
2. **同期エラー** → [トラブルシューティングガイド](troubleshooting.md#同期関連の問題)
3. **パフォーマンス問題** → [トラブルシューティングガイド](troubleshooting.md#パフォーマンス関連の問題)

### サポート
- **ドキュメント**: `docs/` ディレクトリ内の各種ガイド
- **ログ確認**: `logs/bulk_user_management.log`
- **設定検証**: `python scripts/validate_config.py`

## 開発・拡張

### アーキテクチャ
- **モジュラー設計**: 各機能が独立したサービスとして実装
- **プラガブル**: 新しい同期先やテンプレートの追加が容易
- **拡張可能**: APIベースで外部システムとの連携が可能

### カスタマイズポイント
- ユーザー作成ロジック
- 同期プロトコル
- 設定テンプレート
- 認証・認可機構

## ライセンス

このプロジェクトは[ライセンス名]の下で公開されています。

## 更新履歴

### v1.0.0 (2024-01-15)
- 初期リリース
- 基本的な一括ユーザー作成機能
- Load Testerとの同期機能
- Web管理画面

### 今後の予定
- [ ] 複数Load Tester対応
- [ ] 高度な認証機構
- [ ] パフォーマンス監視強化
- [ ] 自動スケーリング対応