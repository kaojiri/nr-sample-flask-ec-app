# New Relic 監視設定ガイド

このアプリケーションは New Relic APM による監視が設定されています。

## 機能

New Relic により以下の情報が自動的に収集されます：

- **アプリケーションパフォーマンス監視 (APM)**
  - リクエスト/レスポンスタイム
  - スループット
  - エラー率
  - トランザクショントレース

- **データベースクエリ監視**
  - SQL クエリのパフォーマンス
  - スロークエリの検出
  - クエリプランの分析

- **分散トレーシング**
  - リクエストの完全な経路追跡
  - マイクロサービス間の依存関係可視化

- **エラー追跡**
  - 例外の自動キャプチャ
  - スタックトレースの記録

- **ブラウザモニタリング**
  - リアルユーザーモニタリング (RUM)
  - ページロード時間
  - JavaScript エラー

## ローカル環境での設定

### Docker Compose を使用する場合

ライセンスキーは既に `docker-compose.yml` に設定されています：

```yaml
NEW_RELIC_LICENSE_KEY=dc3ab4dd75693d8f2a8f71c02a0a513dFFFFNRAL
NEW_RELIC_APP_NAME=Flask EC App (Local)
```

そのまま起動するだけで New Relic に接続されます：

```bash
./scripts/local-setup.sh
```

### Python 仮想環境を使用する場合

`.env` ファイルに以下を追加：

```bash
NEW_RELIC_LICENSE_KEY=dc3ab4dd75693d8f2a8f71c02a0a513dFFFFNRAL
NEW_RELIC_ENVIRONMENT=development
NEW_RELIC_APP_NAME=Flask EC App (Local)
```

その後、通常通りアプリケーションを起動：

```bash
python run.py
```

## AWS (EKS) 環境での設定

ライセンスキーは既に `k8s/secret.yaml` に設定されています。デプロイ時に自動的に適用されます。

```bash
./scripts/deploy.sh
```

## New Relic ダッシュボードへのアクセス

1. https://one.newrelic.com/ にアクセス
2. ログイン後、APM セクションから「Flask EC App」を選択
3. 以下の情報を確認できます：
   - Overview: アプリケーション全体のパフォーマンス概要
   - Transactions: エンドポイント毎のパフォーマンス
   - Databases: データベースクエリのパフォーマンス
   - Errors: エラーの詳細とスタックトレース
   - Distributed tracing: リクエストの詳細な追跡

## カスタムメトリクスの追加

コード内でカスタムメトリクスを追加することもできます：

```python
import newrelic.agent

# カスタムイベントの記録
@newrelic.agent.function_trace()
def my_function():
    # 関数の実行時間を自動追跡
    pass

# カスタム属性の追加
newrelic.agent.add_custom_attribute('user_tier', 'premium')

# カスタムメトリクスの記録
newrelic.agent.record_custom_metric('Custom/MyMetric', 100)
```

## トラブルシューティング

### データが New Relic に表示されない場合

1. ライセンスキーが正しく設定されているか確認：
   ```bash
   # ローカル環境
   docker-compose exec web env | grep NEW_RELIC

   # Kubernetes
   kubectl exec -n flask-ec-app deployment/flask-ec-app -- env | grep NEW_RELIC
   ```

2. New Relic エージェントが正しく初期化されているか確認：
   ```bash
   # ログを確認
   docker-compose logs web | grep -i newrelic

   # Kubernetes
   kubectl logs -n flask-ec-app deployment/flask-ec-app | grep -i newrelic
   ```

3. ネットワーク接続を確認：
   New Relic エージェントは `collector.newrelic.com` に接続する必要があります

### ログレベルの変更

デバッグ情報を増やしたい場合は、`newrelic.ini` の `log_level` を変更：

```ini
log_level = debug
```

## New Relic の無効化

New Relic を無効化したい場合は、環境変数 `NEW_RELIC_LICENSE_KEY` を削除してください：

```bash
# docker-compose.yml から削除
# または
unset NEW_RELIC_LICENSE_KEY
```

## 監視対象のエンドポイント

以下のエンドポイントが自動的に監視されます：

- `GET /` - トップページ
- `GET /products` - 商品一覧
- `GET /products/<id>` - 商品詳細
- `POST /auth/login` - ログイン
- `POST /auth/register` - 会員登録
- `GET /cart` - カート表示
- `POST /cart/add/<id>` - カート追加
- `POST /cart/checkout` - 注文確定
- `GET /health` - ヘルスチェック

## ベストプラクティス

1. **環境別のアプリケーション名**
   - 開発: `Flask EC App (Local)` または `Flask EC App (Dev)`
   - ステージング: `Flask EC App (Staging)`
   - 本番: `Flask EC App`

2. **アラート設定**
   New Relic UI でアラート条件を設定することを推奨：
   - エラー率が 5% を超えた場合
   - レスポンスタイムが 1秒を超えた場合
   - Apdex スコアが 0.8 未満の場合

3. **セキュリティ**
   - ライセンスキーは環境変数で管理
   - `high_security = true` を有効化することも可能（`newrelic.ini`）

## 参考リンク

- [New Relic Python Agent ドキュメント](https://docs.newrelic.com/docs/agents/python-agent/)
- [New Relic APM](https://docs.newrelic.com/docs/apm/)
- [分散トレーシング](https://docs.newrelic.com/docs/distributed-tracing/)
