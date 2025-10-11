# New Relic クイックフィックス

## 問題
ログに `App name: %(NEW_RELIC_APP_NAME)s` と表示され、環境変数が展開されていない。

## 原因
`newrelic.ini` の `%(VAR)s` 構文は ConfigParser の設定ファイル内参照であり、**環境変数ではありません**。

New Relic Python エージェントは環境変数を自動展開しないため、文字列がそのまま使われていました。

## 修正内容

### newrelic.ini の変更
**変更前（間違い）**:
```ini
app_name = %(NEW_RELIC_APP_NAME)s  # ← これは環境変数ではない
```

**変更後（正しい）**:
```ini
app_name = Flask-EC-App  # ← デフォルト値
# 環境変数 NEW_RELIC_APP_NAME があれば自動的に上書きされる
```

## 設定の優先順位

New Relic Python エージェントは以下の順序で設定を読み込みます：

1. **環境変数**（最優先）← `NEW_RELIC_APP_NAME=Flask-EC-App-Local`
2. **newrelic.ini** ← `app_name = Flask-EC-App`
3. **デフォルト値**

したがって：
- ローカル環境: 環境変数 `Flask-EC-App-Local` が使われる ✅
- 環境変数なし: `newrelic.ini` の `Flask-EC-App` が使われる ✅

## 再ビルドして確認

```bash
cd flask-ec-app

# 完全に再ビルド
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# ログ確認（数秒待ってから）
docker-compose logs web | head -60
```

## 期待されるログ出力

**修正後**:
```
==========================================
Starting with New Relic monitoring...
License Key: a6d33b77592503eec05c...NRAL
License Key Length: 44 characters
App Name: Flask-EC-App-Local              ← ✅ 正しい値
Environment: development
==========================================
...
Testing New Relic configuration...
Config loaded successfully!
  License key configured: Yes
  App name: Flask-EC-App-Local            ← ✅ 正しい値
  Monitor mode: True
  Host: collector.newrelic.com
```

**修正前（間違い）**:
```
App name: %(NEW_RELIC_APP_NAME)s          ← ❌ 展開されていない
```

## トラブルシューティング

### テストスクリプトで確認

```bash
docker-compose exec web python test-newrelic.py
```

このスクリプトが：
- 環境変数の設定を確認
- app_name が正しく設定されているか検証
- New Relic への接続をテスト

### まだエラーが出る場合

1. **キャッシュを完全にクリア**:
   ```bash
   docker-compose down -v
   docker system prune -f
   docker-compose build --no-cache
   docker-compose up -d
   ```

2. **環境変数を確認**:
   ```bash
   docker-compose exec web env | grep NEW_RELIC
   ```

   以下が表示されるはず:
   ```
   NEW_RELIC_LICENSE_KEY=a6d33b77592503eec05cb18b178f8928FFFFNRAL
   NEW_RELIC_APP_NAME=Flask-EC-App-Local
   NEW_RELIC_ENVIRONMENT=development
   ```

3. **設定ファイルを確認**:
   ```bash
   docker-compose exec web cat newrelic.ini | grep "app_name"
   ```

   以下が表示されるはず:
   ```
   app_name = Flask-EC-App
   ```

## 参考情報

- New Relic は環境変数を**自動的に**設定ファイルの値より優先します
- `%(VAR)s` 構文は Python ConfigParser の機能で、同じファイル内の他のセクションを参照するもの
- 環境変数を使うには、単に環境変数を設定するだけでOK（特別な構文は不要）

## 成功の確認

5-10分後に https://one.newrelic.com/ の APM セクションで「**Flask-EC-App-Local**」が表示されれば成功です。
