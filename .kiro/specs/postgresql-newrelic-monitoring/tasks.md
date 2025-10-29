# 実装計画

- [x] 1. New Relic Infrastructure Agent設定ファイルの作成
  - newrelic/newrelic-infra.yml基本設定ファイルを作成
  - Infrastructure Agentの基本動作設定を定義
  - ライセンスキーと表示名の環境変数設定を含める
  - _要件: 1.1, 4.1, 4.4_

- [x] 2. PostgreSQL統合設定ファイルの作成
  - newrelic/postgresql-config.yml統合設定ファイルを作成
  - PostgreSQL接続情報を環境変数で設定
  - On-Host Integrationの有効化設定を含める
  - Query Performance Monitoringの設定を含める
  - _要件: 2.1, 2.2, 2.3, 3.1, 3.2_

- [x] 3. Docker Compose設定の更新
  - docker-compose.ymlにnewrelic-infraサービスを追加
  - 適切な環境変数設定を定義
  - 設定ファイルのボリュームマウントを設定
  - PostgreSQLサービスへの依存関係を設定
  - 既存ネットワークへの接続を設定
  - _要件: 1.1, 1.2, 1.5, 4.2_

- [x] 4. 環境変数設定の更新
  - .env.exampleファイルにNew Relic Infrastructure Agent用の環境変数を追加
  - PostgreSQL接続情報の環境変数を定義
  - 設定オーバーライド用の環境変数を追加
  - _要件: 4.1, 4.2, 4.3_

- [x] 5. 設定説明書の作成
  - newrelic/README.mdに設定手順を記載
  - 環境変数の説明を含める
  - トラブルシューティング情報を追加
  - New Relicダッシュボードでの確認方法を記載
  - _要件: 4.4_

- [x] 6. 統合テストの作成
  - Infrastructure Agentの起動確認テストを作成
  - PostgreSQL接続確認テストを作成
  - メトリクス収集動作確認テストを作成
  - _要件: 1.3, 2.5, 3.5_

- [x] 7. エラーハンドリングテストの作成
  - 環境変数不足時のエラーハンドリングテストを作成
  - PostgreSQL接続失敗時の動作確認テストを作成
  - 設定ファイル不正時のエラー確認テストを作成
  - _要件: 4.4, 4.5_