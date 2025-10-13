# Task 4 Implementation Summary

## エンドポイント選択とHTTPクライアント機能を実装

### 実装内容

#### 4.1 エンドポイント選択ロジックの実装 ✅

**新規ファイル: `endpoint_selector.py`**

- **EndpointConfig**: エンドポイント設定を管理するデータクラス
- **EndpointStats**: エンドポイント統計を追跡するデータクラス  
- **EndpointSelector**: メインのエンドポイント選択クラス

**主要機能:**
- 重み付きランダム選択アルゴリズム (`random.choices` を使用)
- パフォーマンス問題エンドポイントの定義:
  - `/performance/slow` - 遅い処理エンドポイント
  - `/performance/n-plus-one` - N+1問題エンドポイント
  - `/performance/slow-query` - スロークエリエンドポイント
  - `/performance/js-errors` - JavaScriptエラーエンドポイント
  - `/performance/bad-vitals` - Core Web Vitals問題エンドポイント
- エンドポイント統計の追跡 (リクエスト数、成功率、平均レスポンス時間)
- 設定ファイルとの連携 (重み付け設定の永続化)

#### 4.2 非同期HTTPクライアントの実装 ✅

**新規ファイル: `http_client.py`**

- **RequestStatus**: リクエスト結果の状態を表すEnum
- **RequestResult**: HTTPリクエスト結果を格納するデータクラス
- **AsyncHTTPClient**: 非同期HTTPクライアントのメインクラス
- **RequestLogger**: リクエスト/レスポンスのログ記録クラス

**主要機能:**
- `aiohttp` を使用した非同期HTTPリクエスト送信
- 包括的なタイムアウト処理:
  - 接続タイムアウト (10秒)
  - 総リクエストタイムアウト (設定可能、デフォルト30秒)
  - ソケット読み取りタイムアウト
- エラーハンドリング:
  - `TimeoutError` - リクエストタイムアウト
  - `ClientConnectionError` - 接続エラー
  - `ClientError` - HTTPクライアントエラー
  - 一般的な例外処理
- リクエスト/レスポンスの詳細ログ記録
- 接続プール管理 (最大接続数制限)
- レスポンス時間とサイズの測定

### API拡張

**更新ファイル: `api.py`**

新しいエンドポイント:
- `GET /api/endpoints` - 全エンドポイント設定と統計の取得
- `GET /api/endpoints/select` - 重み付きランダムエンドポイント選択
- `POST /api/endpoints/weights` - エンドポイント重み付けの更新
- `GET /api/endpoints/stats` - エンドポイント統計の取得
- `POST /api/endpoints/reload` - エンドポイント設定の再読み込み

### 設定管理拡張

**更新ファイル: `config.py`**

- `target_app_url` をメイン設定に追加
- エンドポイント設定の永続化サポート

### テスト・検証

**新規ファイル:**
- `test_endpoint_selection.py` - 統合テスト (外部依存関係が必要)
- `verify_endpoint_logic.py` - 基本ロジック検証 (依存関係なし)

**検証結果:**
- 重み付きランダム選択が正しく動作することを確認
- 設定構造が適切に機能することを確認
- 統計計算が正確に動作することを確認

### 要件対応

#### Requirements 2.1, 2.2 対応:
- ✅ パフォーマンス問題エンドポイントからのランダム選択
- ✅ 設定可能な重み付けに基づく選択
- ✅ エンドポイント統計の追跡

#### Requirements 1.1, 1.2, 2.4 対応:
- ✅ 非同期HTTPリクエスト送信機能
- ✅ タイムアウト処理とエラーハンドリング
- ✅ リクエスト/レスポンスのログ記録

### 次のステップ

この実装により、負荷テスト実行エンジン (Task 5) で使用する基盤が整いました:

1. **エンドポイント選択**: `endpoint_selector.select_endpoint()` でランダムエンドポイント取得
2. **HTTPリクエスト**: `AsyncHTTPClient` で非同期リクエスト送信
3. **統計追跡**: `endpoint_selector.update_endpoint_stats()` で結果記録
4. **設定管理**: 重み付けやエンドポイント有効/無効の動的変更

Task 5 では、これらのコンポーネントを組み合わせて実際の負荷テスト実行機能を実装します。