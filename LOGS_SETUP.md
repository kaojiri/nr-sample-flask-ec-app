# New Relic Logs in Context & Browser Logs セットアップガイド

このアプリケーションは New Relic Logs in Context と Browser Logs をサポートしています。

## 📝 Python ログ（Logs in Context）

### 実装内容

#### 1. ロギング設定
[app/logging_config.py](app/logging_config.py) でカスタムロガーを設定：
- リクエストコンテキスト（URL, メソッド, IP, User-Agent）を自動追加
- 構造化ログ（extra フィールドで追加情報）
- New Relic が自動的にキャプチャ

#### 2. ログ出力箇所

| 箇所 | ログイベント | 確認できる情報 |
|------|------------|-------------|
| **ホームページ** (`/`) | `page_view`, `data_loaded` | アクセス情報、商品数 |
| **商品一覧** (`/products`) | `page_view`, `data_loaded` | ページ番号、カテゴリ、商品数 |
| **商品詳細** (`/products/<id>`) | `product_viewed` | 商品ID、名前、価格、在庫 |
| **カート表示** (`/cart`) | `cart_viewed` | ユーザーID、アイテム数、合計金額 |
| **カート追加** (`/cart/add`) | `cart_add`, `cart_add_success` | 商品ID、数量、価格 |
| **チェックアウト** (`/cart/checkout`) | `order_create`, `order_success` | 注文ID、合計金額、アイテム数 |
| **パフォーマンス問題** (`/performance/*`) | `slow_transaction`, `error_demo` など | 遅延時間、エラー詳細 |

#### 3. ログレベル
- `INFO`: 通常の操作（ページビュー、データ読み込み）
- `WARNING`: 問題の兆候（遅い処理、空のカート）
- `ERROR`: エラー発生
- `DEBUG`: 詳細なデバッグ情報

### New Relic での確認方法

#### APM Logs in Context

1. **APM → Logs タブ**を開く
2. ログが自動的に表示される
3. フィルター例：
   ```
   event_type:page_view
   event_type:order_success
   event_type:cart_add
   ```

4. **Transaction と紐付けて表示**：
   - APM → Transactions で特定のトランザクションを選択
   - "See logs" をクリック
   - そのトランザクション中に出力されたログが表示される

#### ログクエリ例

```sql
-- ページビューの集計
SELECT count(*) FROM Log WHERE event_type = 'page_view' FACET page

-- 注文の成功回数
SELECT count(*) FROM Log WHERE event_type = 'order_success' SINCE 1 hour ago

-- 遅い処理の検知
SELECT * FROM Log WHERE event_type = 'slow_transaction_start' SINCE 1 hour ago

-- エラーログ
SELECT * FROM Log WHERE level = 'ERROR' SINCE 1 hour ago
```

---

## 🌐 Browser Logs

### 実装内容

#### 1. 自動ログ収集
[app/templates/base.html](app/templates/base.html) で以下を実装：

- **JavaScript エラー** - 自動キャプチャ
- **Unhandled Promise Rejection** - 自動キャプチャ
- **ページロード** - 自動ログ
- **パフォーマンスメトリクス** - Page Load Time, DOM Ready Time, TTFB

#### 2. カスタムログ関数
```javascript
// JavaScript でログを送信
window.logToNewRelic('info', 'User clicked button', {
    button_id: 'submit',
    user_action: 'form_submit'
});
```

#### 3. 自動収集されるイベント
- ページビュー（URL, リファラー）
- JavaScript エラー（スタックトレース付き）
- パフォーマンスメトリクス（ロード時間）
- ユーザーインタラクション

### Browser Monitoring の有効化（必須）

Browser Logs を使用するには、Browser Monitoring を有効化する必要があります。

#### 手順

1. **New Relic UI にログイン**
   https://one.newrelic.com/

2. **Browser アプリケーションを作成**
   - Browser → "Add a browser app" をクリック
   - アプリ名: `Flask-EC-App-Browser` (例)
   - デプロイ方法: "Copy/paste JavaScript code" を選択

3. **JavaScript スニペットを取得**
   以下のようなコードが表示されます：
   ```html
   <script type="text/javascript">
   window.NREUM||(NREUM={});NREUM.init={...};
   window.NREUM||(NREUM={}),__nr_require=function(...){...}
   </script>
   ```

4. **base.html に貼り付け**
   [app/templates/base.html](app/templates/base.html) の以下の部分を置き換え：
   ```html
   <!-- New Relic Browser Monitoring - Placeholder -->
   <!--
   To enable Browser Monitoring and Browser Logs:
   ...
   -->
   ```

   ↓

   ```html
   <!-- New Relic Browser Monitoring -->
   <script type="text/javascript">
   // ここに取得したスニペットを貼り付け
   </script>
   ```

5. **再ビルドして起動**
   ```bash
   cd /Users/kaizawa/Desktop/mcp-test/flask-ec-app
   ./scripts/rebuild-and-start.sh
   ```

6. **確認**
   - ブラウザで http://localhost:5001 にアクセス
   - 開発者ツール → Console で `window.newrelic` が存在することを確認
   - 5-10分後に New Relic UI の Browser セクションでデータを確認

### New Relic Browser での確認方法

#### Browser Logs

1. **Browser → Logs タブ**を開く
2. JavaScript から送信されたログが表示される
3. フィルター例：
   ```
   level:info
   event_type:performance
   page:products
   ```

#### JavaScript Errors

1. **Browser → JS errors タブ**を開く
2. エラーの発生頻度、スタックトレースを確認
3. どのページで発生しているかを確認

#### Session Traces

1. **Browser → Session traces タブ**を開く
2. ユーザーのセッション全体を再現
3. ページ遷移、クリック、エラーを時系列で確認

---

## 🔍 ログ確認デモ

### シナリオ 1: ユーザーが商品を購入する流れ

1. ホームページにアクセス → `page_view: home`
2. 商品一覧を表示 → `page_view: products_list`
3. 商品詳細を表示 → `product_viewed`
4. カートに追加 → `cart_add`, `cart_add_success`
5. カートを表示 → `cart_viewed`
6. チェックアウト → `order_create`, `order_success`

**New Relic で確認**:
```sql
SELECT * FROM Log
WHERE user_id = '<ユーザーID>'
ORDER BY timestamp
SINCE 10 minutes ago
```

ユーザーの一連の行動が時系列で表示されます。

### シナリオ 2: エラーの追跡

1. `/performance/error` にアクセス
2. Python でエラーログが出力される
3. APM でエラーが記録される
4. Logs in Context でエラーの詳細を確認

**New Relic で確認**:
- APM → Errors → 特定のエラーを選択
- "See logs" でそのトランザクションのログを表示
- エラー発生前後の状況を分析

### シナリオ 3: パフォーマンス問題の調査

1. `/performance/slow` にアクセス
2. ログに遅延開始・完了が記録される
3. APM で slow transaction として記録される

**New Relic で確認**:
```sql
SELECT * FROM Log
WHERE event_type = 'slow_transaction_start'
OR event_type = 'slow_transaction_complete'
SINCE 1 hour ago
```

遅延の詳細（何秒遅延したか）を確認できます。

---

## 📊 ログの活用例

### ビジネスインサイト

#### 人気商品の分析
```sql
SELECT product_name, count(*) as views
FROM Log
WHERE event_type = 'product_viewed'
FACET product_name
SINCE 1 day ago
```

#### 購入コンバージョン率
```sql
SELECT
  (SELECT count(*) FROM Log WHERE event_type = 'order_success') /
  (SELECT count(*) FROM Log WHERE event_type = 'cart_add') * 100
  as conversion_rate
SINCE 1 day ago
```

#### カート放棄率
```sql
SELECT
  (SELECT count(*) FROM Log WHERE event_type = 'cart_viewed') -
  (SELECT count(*) FROM Log WHERE event_type = 'order_success')
  as abandoned_carts
SINCE 1 day ago
```

### パフォーマンス分析

#### 遅いページの特定
```sql
SELECT average(page_load_time), page
FROM Log
WHERE event_type = 'performance'
FACET page
SINCE 1 hour ago
```

#### データベースクエリの分析
APM Logs と組み合わせて、どのエンドポイントでどのクエリが実行されているかを確認。

---

## 🔧 トラブルシューティング

### Python ログが表示されない

1. **New Relic エージェントが起動しているか確認**:
   ```bash
   docker-compose logs web | grep -i "new relic"
   ```

2. **ログレベルを確認**:
   ```bash
   docker-compose exec web python -c "
   import logging
   from flask import Flask
   from app import create_app
   app = create_app()
   print('Log level:', app.logger.level)
   "
   ```

3. **手動でログを送信してテスト**:
   ```bash
   docker-compose exec web python -c "
   from app import create_app
   app = create_app()
   with app.app_context():
       app.logger.info('Test log message', extra={'test': True})
   "
   ```

### Browser Logs が表示されない

1. **Browser Monitoring が有効か確認**:
   - ブラウザの開発者ツールで `window.newrelic` が存在するか確認
   ```javascript
   console.log(window.newrelic);
   ```

2. **JavaScript スニペットが正しく挿入されているか確認**:
   - ページのソースを表示して `<script type="text/javascript">window.NREUM...` を探す

3. **ネットワークタブで確認**:
   - 開発者ツール → Network タブ
   - `bam.nr-data.net` へのリクエストがあるか確認

---

## 📚 参考リンク

- [New Relic Logs in Context](https://docs.newrelic.com/docs/logs/logs-context/logs-in-context/)
- [New Relic Browser Monitoring](https://docs.newrelic.com/docs/browser/)
- [Browser Agent API](https://docs.newrelic.com/docs/browser/new-relic-browser/browser-apis/using-browser-apis/)
- [Logs Query Language (NRQL)](https://docs.newrelic.com/docs/nrql/using-nrql/introduction-nrql-new-relics-query-language/)

---

## ✅ チェックリスト

- [ ] Python ログが New Relic APM Logs に表示される
- [ ] Transaction とログが紐付いている
- [ ] Browser Monitoring JavaScript が挿入されている
- [ ] Browser Logs が New Relic Browser Logs に表示される
- [ ] JavaScript エラーが記録される
- [ ] パフォーマンスメトリクスが記録される
- [ ] カスタムログクエリが実行できる
