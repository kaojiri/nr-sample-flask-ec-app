# New Relic検証機能 実装ドキュメント

## 概要

分散トレーシングサービスのNew Relic監視機能を自動検証するためのシステムを実装しました。この機能により、分散トレーシングヘッダーの伝播、Custom Attributeの設定、パフォーマンス問題の検出を自動的に検証できます。

## 実装されたファイル

### 1. `newrelic_verification.py`
New Relic API連携機能の中核となるモジュール

**主要クラス:**
- `NewRelicAPIClient`: New Relic APIとの通信を担当
- `NewRelicVerificationService`: 検証機能の統合サービス
- `TraceData`, `PerformanceMetrics`: データ構造定義

**主要機能:**
- 分散トレーシングデータの取得
- Custom Attributeの自動検証
- エラー追跡データの確認
- パフォーマンスメトリクスの検証
- 総合レポートの生成

### 2. `automated_test_scenarios.py`
自動化されたテストシナリオの実装

**主要クラス:**
- `DistributedTracingTestScenarios`: 各種テストシナリオの実装
- `AutomatedTestRunner`: テストスイートの実行管理
- `TestScenarioResult`: テスト結果のデータ構造

**実装されたテストシナリオ:**
- 基本的な分散トレーシング機能テスト
- N+1クエリ問題の自動検証テスト
- スロークエリ問題の自動検証テスト
- データベースエラー問題の自動検証テスト

### 3. `run_automated_verification.py`
自動化テストの実行スクリプト

**機能:**
- コマンドライン引数による柔軟な実行制御
- 事前定義されたテストスイートの実行
- 結果の詳細表示とファイル保存
- システム状態の確認

### 4. `distributed_service_client.py` (更新)
同期版のテストクライアントを追加

**追加クラス:**
- `SyncDistributedServiceTestClient`: 自動化テスト用の同期版クライアント

## 設定

### 環境変数
```bash
export NEW_RELIC_API_KEY="your_api_key_here"
export NEW_RELIC_ACCOUNT_ID="your_account_id_here"
```

### config.json設定
```json
{
  "newrelic_verification": {
    "enabled": true,
    "api_key": "${NEW_RELIC_API_KEY}",
    "account_id": "${NEW_RELIC_ACCOUNT_ID}",
    "app_names": [
      "Flask-EC-Main-App",
      "Flask-EC-Distributed-Service"
    ],
    "verification_timeout_seconds": 300,
    "retry_attempts": 3,
    "retry_delay_seconds": 10
  }
}
```

## 使用方法

### 1. 基本的な検証テスト
```bash
python3 load-tester/run_automated_verification.py basic_verification
```

### 2. パフォーマンス問題検証テスト
```bash
python3 load-tester/run_automated_verification.py performance_verification
```

### 3. 包括的検証テスト
```bash
python3 load-tester/run_automated_verification.py comprehensive_verification
```

### 4. カスタムユーザー数での実行
```bash
python3 load-tester/run_automated_verification.py basic_verification --users 10
```

### 5. 利用可能なテストスイート一覧
```bash
python3 load-tester/run_automated_verification.py --list
```

### 6. システム状態確認
```bash
python3 load-tester/run_automated_verification.py --status
```

## 事前定義されたテストスイート

### basic_verification
- **目的**: 基本的な分散トレーシング機能の検証
- **シナリオ**: basic_distributed_tracing
- **テストユーザー数**: 5
- **実行時間**: 約2-3分

### performance_verification
- **目的**: パフォーマンス問題の検出機能検証
- **シナリオ**: n_plus_one_verification, slow_query_verification, database_error_verification
- **テストユーザー数**: 3
- **実行時間**: 約5-7分

### comprehensive_verification
- **目的**: 全機能の包括的検証
- **シナリオ**: 全シナリオ
- **テストユーザー数**: 5
- **実行時間**: 約8-10分

## 検証項目

### 1. 分散トレーシングヘッダー伝播
- メインアプリケーションから分散サービスへのトレース連携
- New Relicでの分散トレーシング表示確認
- トレースIDの一貫性検証

### 2. Custom Attribute設定
- userIdのCustom Attribute設定確認
- 各サービスでのCustom Attribute表示検証
- エラー時のCustom Attribute保持確認

### 3. パフォーマンス問題検出
- N+1クエリ問題の検出確認
- スロークエリの監視確認
- データベースエラーの追跡確認

## 出力例

```
テスト結果サマリー
============================================================
テストスイート: Basic Distributed Tracing Verification
全体ステータス: success
実行時間: 125.34 秒

サマリー:
  シナリオ数: 1
  成功: 1
  部分成功: 0
  失敗: 0
  リクエスト成功率: 100.00%

シナリオ別結果:
------------------------------------------------------------
✓ basic_distributed_tracing
    ステータス: success
    実行時間: 89.45 秒
    成功リクエスト: 10/10
    平均レスポンス時間: 1234.56 ms

New Relic検証結果:
------------------------------
  分散トレーシング: ✓
  Custom Attribute: ✓
  パフォーマンス問題: ✓
```

## トラブルシューティング

### 1. New Relic API接続エラー
- 環境変数の設定確認
- APIキーの有効性確認
- ネットワーク接続確認

### 2. 分散サービス接続エラー
- 分散サービスの起動状態確認
- ネットワーク設定確認
- エンドポイントURL確認

### 3. 検証結果が期待と異なる場合
- New Relicでのデータ遅延を考慮（通常1-2分）
- アプリケーション名の設定確認
- Custom Attributeの設定確認

## 依存関係

```
requests>=2.25.0
aiohttp>=3.9.1
pydantic>=2.5.0
pydantic-settings>=2.1.0
```

## ログファイル

- テスト結果: `logs/automated_verification_*.json`
- 分散サービステスト: `logs/distributed_service_tests.log`
- 一般ログ: `logs/requests.log`

## 今後の拡張可能性

1. **追加のパフォーマンス問題シナリオ**
   - メモリリーク検出
   - CPU使用率監視
   - ネットワーク遅延シミュレーション

2. **より詳細な検証機能**
   - SLAベースの検証
   - アラート設定の自動検証
   - ダッシュボード表示の確認

3. **CI/CD統合**
   - GitHub Actions統合
   - 自動レポート生成
   - Slack通知機能

4. **マルチ環境対応**
   - 開発/ステージング/本番環境の切り替え
   - 環境別設定管理
   - クロス環境検証

## 実装完了項目

✅ New Relic API連携機能の実装  
✅ 分散トレーシング検証機能の実装  
✅ Custom Attribute自動検証機能の実装  
✅ エラー追跡データ確認機能の実装  
✅ パフォーマンスメトリクス検証機能の実装  
✅ 自動化されたテストシナリオの実装  
✅ 分散トレーシングヘッダー伝播の自動検証  
✅ userIdのCustom Attribute設定の自動確認  
✅ パフォーマンス問題シナリオの実行結果検証  
✅ コマンドライン実行スクリプトの実装  
✅ 総合レポート生成機能の実装  

この実装により、分散トレーシングサービスのNew Relic監視機能を包括的に自動検証できるシステムが完成しました。