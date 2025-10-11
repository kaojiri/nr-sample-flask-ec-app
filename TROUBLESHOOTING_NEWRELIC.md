# New Relic トラブルシューティング

## エラー: "Data collector is indicating that an incorrect license key has been supplied"

### 重要な訂正

**Ingest - LICENSE キーは APM エージェントでも使用できます！**

現在の New Relic では、以下のキータイプがあります：
- **User API Key**: ユーザー認証用
- **Ingest - LICENSE**: データ取り込み用（**APM エージェントでも使用可能**）✅
- **Ingest - BROWSER**: Browser monitoring 専用

末尾が `NRAL` の **Ingest - LICENSE キーは APM で使用できます**。

### 実際の原因

このエラーメッセージが出る主な原因：

1. **設定ファイルの問題**
   - 環境変数が正しく渡されていない
   - newrelic.ini の構文エラー
   - アプリケーション名の形式エラー

2. **二重初期化**
   - run.py と newrelic-admin の両方で初期化している
   - 設定が競合している

3. **ネットワーク問題**
   - collector.newrelic.com への接続がブロックされている
   - プロキシ設定が必要な環境

4. **環境変数の展開エラー**
   - newrelic.ini で `%(NEW_RELIC_APP_NAME)s` が正しく展開されない
   - 環境変数がコンテナに渡されていない

## 解決方法

### 1. ライセンスキーの確認

**Ingest - LICENSE キー（末尾が NRAL）は使用可能です！**

New Relic でキーを取得：
1. https://one.newrelic.com/ にログイン
2. 右上のユーザーメニュー → **API keys**
3. **Ingest - LICENSE** タイプのキーを使用

キーの形式（どちらも有効）：
```
# ✅ Ingest - LICENSE キー（末尾が NRAL）
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxNRAL

# ✅ レガシー License Key（40文字）
1234567890abcdef1234567890abcdef12345678
```

### 2. 環境変数を更新

**ローカル環境 (docker-compose.yml)**:
```yaml
environment:
  - NEW_RELIC_LICENSE_KEY=<あなたのライセンスキー>
  - NEW_RELIC_APP_NAME=Flask-EC-App-Local
  - NEW_RELIC_ENVIRONMENT=development
```

**本番環境 (k8s/secret.yaml)**:
```yaml
stringData:
  NEW_RELIC_LICENSE_KEY: "<あなたのライセンスキー>"
```

### 3. 接続テストを実行

まず、New Relic の設定をテスト：

```bash
cd flask-ec-app

# コンテナ内でテスト実行
docker-compose exec web python test-newrelic.py
```

このスクリプトは以下を確認します：
- ライセンスキーが設定されているか
- New Relic エージェントが正しくインポートできるか
- 設定ファイルが存在するか
- 初期化が成功するか

### 4. 完全に再ビルドして起動

設定を変更した場合は、必ず再ビルド：

```bash
cd flask-ec-app

# 完全に再ビルド
./scripts/rebuild-and-start.sh

# または手動で
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# ログで詳細な起動情報を確認
docker-compose logs web | grep -A 20 "New Relic"
```

### 5. デバッグログを確認

start.sh で詳細なデバッグ情報が出力されます：

```bash
docker-compose logs web
```

以下の情報が表示されるはずです：
```
==========================================
Starting with New Relic monitoring...
License Key: a6d33b77592503eec05c...NRAL
License Key Length: 44 characters
App Name: Flask-EC-App-Local
Environment: development
==========================================
Configuration:
  Config File: /app/newrelic.ini
  Log Level: debug

Verifying New Relic installation...
New Relic version: 9.5.0

Testing New Relic configuration...
Config loaded successfully!
  License key configured: Yes
  App name: Flask-EC-App-Local
  Monitor mode: True
  Host: collector.newrelic.com
```

## 修正された問題

このアプリケーションでは以下の問題を修正しました：

### 1. 二重初期化の削除
**問題**: `run.py` と `start.sh` の両方で New Relic を初期化していた

**修正**: [run.py](run.py:1-2)
```python
# New Relic initialization is handled by newrelic-admin in start.sh
# Do not initialize here to avoid double initialization
```

### 2. app_name の環境変数対応
**問題**: `newrelic.ini` で app_name が固定値だった

**修正**: [newrelic.ini](newrelic.ini:33)
```ini
app_name = %(NEW_RELIC_APP_NAME)s
```

### 3. 詳細なデバッグ情報
**追加**: [start.sh](start.sh) で以下を実装
- ライセンスキーの長さと形式の確認
- New Relic バージョンの表示
- 設定の事前テスト
- 詳細なエラーメッセージ

### 4. 接続テストスクリプト
**追加**: [test-newrelic.py](test-newrelic.py)
- 独立した接続テストツール
- 起動前に設定を検証可能

## New Relic UI での確認方法

1. **API Keys ページ**: https://one.newrelic.com/launcher/api-keys-ui.api-keys-launcher
2. **APM ダッシュボード**: https://one.newrelic.com/launcher/nr1-core.explorer?pane=eyJuZXJkbGV0SWQiOiJucjEtY29yZS5saXN0aW5nIn0=

アプリケーションが正常に接続されると、5-10分後に以下のように表示されます：
- APM & Services セクションに「Flask-EC-App-Local」が表示
- トランザクション、エラー、ログなどが記録される

## よくある問題と解決方法

### 問題 1: 環境変数が設定されていない

**確認方法**:
```bash
docker-compose exec web env | grep NEW_RELIC
```

**解決方法**: `docker-compose.yml` を確認して再起動

### 問題 2: 設定ファイルの構文エラー

**確認方法**:
```bash
docker-compose exec web python -c "
import configparser
config = configparser.ConfigParser()
config.read('newrelic.ini')
print('Config sections:', config.sections())
"
```

### 問題 3: ネットワーク接続の問題

**確認方法**:
```bash
docker-compose exec web ping -c 3 collector.newrelic.com
```

**解決方法**:
- ファイアウォール設定を確認
- プロキシが必要な場合は newrelic.ini で設定

### 問題 4: キーに余分なスペースや改行

**確認方法**:
```bash
docker-compose exec web python -c "
import os
key = os.getenv('NEW_RELIC_LICENSE_KEY')
print(f'Length: {len(key)}')
print(f'Has spaces: {\" \" in key}')
print(f'Has newlines: {chr(10) in key}')
"
```

## データが表示されるまでの時間

New Relic にデータが表示されるまで：
- **最初の接続**: 5-10分
- **その後**: ほぼリアルタイム（数秒～1分）

すぐに表示されない場合は、アプリケーションにアクセスしてトラフィックを生成してください：
```bash
# ローカルで複数回アクセス
for i in {1..10}; do curl http://localhost:5001/; done
```

## サポートへの問い合わせ

上記で解決しない場合、以下の情報を添えて New Relic サポートに連絡：

1. **アカウント情報**
   - アカウント ID
   - 使用しているライセンスキーの種類（Ingest-LICENSE）

2. **エージェント情報**
   ```bash
   docker-compose exec web pip show newrelic
   ```

3. **完全なログ**
   ```bash
   docker-compose logs web > newrelic-logs.txt
   ```

4. **設定ファイル**（ライセンスキーは隠す）
   - docker-compose.yml
   - newrelic.ini の内容

## 参考リンク

- [New Relic License Key Documentation](https://docs.newrelic.com/docs/apis/intro-apis/new-relic-api-keys/#license-key)
- [Python Agent Configuration](https://docs.newrelic.com/docs/apm/agents/python-agent/configuration/python-agent-configuration/)
- [Python Agent Installation](https://docs.newrelic.com/docs/apm/agents/python-agent/installation/python-agent-installation/)
- [Troubleshooting Python Agent](https://docs.newrelic.com/docs/apm/agents/python-agent/troubleshooting/)
