# New Relic 環境変数問題の完全な解決

## 問題
`NEW_RELIC_APP_NAME=Flask-EC-App-Local` を設定しているのに、ログに `App name: Flask-EC-App` と表示され、環境変数が反映されない。

## 根本原因

**New Relic Python エージェントの設定優先順位**（公式ドキュメントより）:

```
1. newrelic.ini の値（最優先） ← これが問題！
2. 環境変数
3. デフォルト値
```

つまり、**`newrelic.ini` に `app_name` が設定されていると、環境変数 `NEW_RELIC_APP_NAME` は完全に無視されます**。

### 間違った理解
❌ 「環境変数が newrelic.ini を上書きする」と思っていた
✅ **実際は「newrelic.ini が環境変数を上書きする」**

## 解決策

### newrelic.ini の修正

**修正前（間違い）**:
```ini
app_name = Flask-EC-App  ← これが環境変数を上書きしていた
```

**修正後（正しい）**:
```ini
# app_name = Flask-EC-App  ← コメントアウト
# 環境変数 NEW_RELIC_APP_NAME を使用
```

`app_name` を `newrelic.ini` から削除することで、環境変数が有効になります。

## 設定の動作

### 修正後の動作
```
環境変数: NEW_RELIC_APP_NAME=Flask-EC-App-Local
newrelic.ini: app_name は未設定（コメントアウト）
↓
結果: Flask-EC-App-Local が使われる ✅
```

### 環境別の設定例

**ローカル環境** (docker-compose.yml):
```yaml
environment:
  - NEW_RELIC_APP_NAME=Flask-EC-App-Local
```
→ New Relic に「Flask-EC-App-Local」として表示

**本番環境** (k8s/deployment.yaml):
```yaml
- name: NEW_RELIC_APP_NAME
  value: "Flask-EC-App-Production"
```
→ New Relic に「Flask-EC-App-Production」として表示

**環境変数なしの場合**:
→ New Relic に「Python Application」（デフォルト）として表示

## 再ビルドして確認

```bash
cd /Users/kaizawa/Desktop/mcp-test/flask-ec-app

# 完全に再ビルド
./scripts/rebuild-and-start.sh

# ログで確認（数秒待ってから）
docker-compose logs web | grep "App name"
```

## 期待される出力

**修正後**:
```
==========================================
Starting with New Relic monitoring...
License Key: a6d33b77592503eec05c...NRAL
License Key Length: 44 characters
App Name: Flask-EC-App-Local              ← ✅ 環境変数の値！
Environment: development
==========================================
...
Testing New Relic configuration...
Config loaded successfully!
  License key configured: Yes
  App name: Flask-EC-App-Local            ← ✅ 正しい値！
  Monitor mode: True
  Host: collector.newrelic.com
```

**修正前（問題）**:
```
App name: Flask-EC-App                    ← ❌ newrelic.ini の値
```

## New Relic UI での確認

5-10分後に https://one.newrelic.com/ の APM セクションで：
- ✅ **Flask-EC-App-Local** が表示される（ローカル環境）
- ✅ **Flask-EC-App-Production** が表示される（本番環境）

## 重要なポイント

### ✅ やるべきこと
- 環境ごとに異なるアプリ名を設定したい場合は、`newrelic.ini` の `app_name` を**削除またはコメントアウト**
- 環境変数 `NEW_RELIC_APP_NAME` で設定

### ❌ やってはいけないこと
- `newrelic.ini` に `app_name` を設定した状態で、環境変数で上書きしようとする
- `%(NEW_RELIC_APP_NAME)s` のような構文を使う（これは環境変数展開ではない）

## トラブルシューティング

### 環境変数が反映されない場合

1. **newrelic.ini を確認**:
   ```bash
   docker-compose exec web cat newrelic.ini | grep "app_name"
   ```

   以下のようになっているはず:
   ```ini
   # app_name = Flask-EC-App  # Commented out
   ```

2. **環境変数を確認**:
   ```bash
   docker-compose exec web env | grep NEW_RELIC_APP_NAME
   ```

   出力:
   ```
   NEW_RELIC_APP_NAME=Flask-EC-App-Local
   ```

3. **実際の設定値を確認**:
   ```bash
   docker-compose exec web python -c "
   import os
   print('Env var:', os.getenv('NEW_RELIC_APP_NAME'))
   import newrelic.agent
   newrelic.agent.initialize('newrelic.ini', environment='development')
   settings = newrelic.agent.global_settings()
   print('Agent app_name:', settings.app_name)
   "
   ```

   期待される出力:
   ```
   Env var: Flask-EC-App-Local
   Agent app_name: Flask-EC-App-Local
   ```

### まだ問題がある場合

`license_key` も同じ問題がある可能性があります。確認してください：

```ini
# newrelic.ini
[newrelic]
# ❌ 間違い - これも環境変数を上書きする
license_key = %(NEW_RELIC_LICENSE_KEY)s

# ✅ 正しい - コメントアウトして環境変数を使う
# license_key = your-license-key
```

ただし、現在 `license_key = %(NEW_RELIC_LICENSE_KEY)s` となっている場合、この構文は**機能しません**（環境変数展開ではない）。

この場合も削除して、環境変数のみで設定する必要があります。

## 参考リンク

- [New Relic Python Agent Configuration](https://docs.newrelic.com/docs/apm/agents/python-agent/configuration/python-agent-configuration/)
- [Python Agent Admin Script](https://docs.newrelic.com/docs/apm/agents/python-agent/installation/python-agent-admin-script-advanced-usage/)
- [New Relic Forum: Environment variable NEW_RELIC_APP_NAME not working](https://forum.newrelic.com/s/hubtopic/aAX8W0000015AuOWAU/environment-variable-newrelicappname-not-working)
