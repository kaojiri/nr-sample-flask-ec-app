# New Relic セットアップガイド

## 問題の原因

現在、New Relicにデータが送信されない理由は、**ダミーのライセンスキー**が設定されているためです。

現在の設定:
```
NEW_RELIC_LICENSE_KEY=7f7e0dafe29017dcdad3b8c608fedfd6FFFFNRAL
```

`FFFFNRAL`で終わるキーはダミーキーです。

## 解決方法

### 1. New Relicライセンスキーの取得

1. **New Relicアカウントにログイン**
   - https://one.newrelic.com/ にアクセス

2. **ライセンスキーを取得**
   - 右上のユーザーメニュー → "API Keys"
   - または直接: https://one.newrelic.com/launcher/api-keys-ui.api-keys-launcher
   - "License keys" タブを選択
   - 既存のキーをコピーするか、新しいキーを作成

3. **正しいライセンスキーの形式**
   ```
   # 正しい形式（40文字の英数字）
   NEW_RELIC_LICENSE_KEY=1234567890abcdef1234567890abcdef12345678
   ```

### 2. 環境変数ファイルの更新

`.env`ファイルを編集して、実際のライセンスキーを設定：

```bash
# .envファイルを編集
nano .env

# または
vim .env
```

以下の行を実際のライセンスキーに変更：
```properties
# 変更前（ダミーキー）
NEW_RELIC_LICENSE_KEY=7f7e0dafe29017dcdad3b8c608fedfd6FFFFNRAL

# 変更後（実際のキー）
NEW_RELIC_LICENSE_KEY=あなたの実際のライセンスキー
```

### 3. サービスの再起動

ライセンスキーを更新した後、サービスを再起動：

```bash
# 全サービスを再起動
docker-compose down
docker-compose up -d

# または再ビルドスクリプトを使用
./scripts/rebuild-and-start.sh
```

### 4. 動作確認

1. **ログでエラーがないことを確認**
   ```bash
   # メインアプリケーションのログ
   docker-compose logs web | grep -i "new relic\|error\|license"
   
   # 分散サービスのログ
   docker-compose logs distributed-service | grep -i "new relic\|error\|license"
   ```

2. **New Relic UIでデータを確認**
   - APM & Services → Flask-EC-App-Local
   - APM & Services → Flask-EC-Distributed-Service

3. **テストリクエストを送信**
   ```bash
   # メインアプリケーションにアクセス
   curl http://localhost:5001/
   
   # 分散サービスにアクセス
   curl http://localhost:5002/health
   
   # パフォーマンスデモを実行
   curl http://localhost:5001/performance/
   ```

## 追加の設定（オプション）

### User Key（Change Tracking用）

Change Tracking機能を使用する場合は、User Keyも更新：

1. New Relic One → API Keys → User Keys
2. 新しいUser Keyを作成またはコピー
3. `.env`ファイルの`NEW_RELIC_API_KEY`を更新

### Entity GUID（Change Tracking用）

1. New Relic One → APM & Services → アプリケーション選択
2. URLまたは設定からEntity GUIDを取得
3. `.env`ファイルの`NEW_RELIC_ENTITY_GUID`を更新

## トラブルシューティング

### よくあるエラー

1. **"incorrect license key"エラー**
   - ライセンスキーが間違っている
   - 40文字の英数字であることを確認

2. **"Registration failed"エラー**
   - ネットワーク接続の問題
   - ファイアウォールの設定を確認

3. **データが表示されない**
   - ライセンスキー更新後、5-10分待つ
   - アプリケーションにトラフィックを送信

### ログの確認方法

```bash
# 詳細なNew Relicログを確認
docker-compose logs web | grep -A5 -B5 "newrelic"
docker-compose logs distributed-service | grep -A5 -B5 "newrelic"

# エラーログのみを確認
docker-compose logs web 2>&1 | grep -i error
docker-compose logs distributed-service 2>&1 | grep -i error
```

## 注意事項

- ライセンスキーは機密情報です。GitHubなどの公開リポジトリにコミットしないでください
- `.env`ファイルは`.gitignore`に含まれていることを確認してください
- 本番環境では環境変数として直接設定することを推奨します