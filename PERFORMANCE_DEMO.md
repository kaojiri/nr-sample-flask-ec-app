# パフォーマンス問題デモ - New Relic 検証用

このアプリケーションには、New Relic のモニタリング機能をデモ・検証するために、**意図的にパフォーマンスの問題を含んだエンドポイント**が用意されています。

⚠️ **警告**: これらのエンドポイントは本番環境では使用しないでください！

## アクセス方法

http://localhost:5001/performance/

## 用意されている問題

### 1. 🐌 遅い処理（Slow Transaction）

**エンドポイント**: `/performance/slow`

**問題内容**:
- レスポンスに 3-5 秒かかる
- 重い計算処理を実行
- 複数の遅延操作

**New Relic で検知できること**:
- Transaction time が異常に高い
- Apdex score が低下
- Slow transaction traces に記録される
- Throughput と Response time の比較

**確認手順**:
1. APM → Transactions タブを開く
2. `/performance/slow` が他のエンドポイントより遅いことを確認
3. Transaction trace をクリックして詳細を確認
4. どの処理で時間がかかっているかを分析

---

### 2. 🔄 N+1 クエリ問題

**エンドポイント**:
- `/performance/n-plus-one` (問題あり)
- `/performance/n-plus-one-fixed` (修正版)

**問題内容**:
- 20個の商品に対して 40回以上のデータベースクエリを実行
- 各商品ごとに個別にクエリを発行（N+1 問題）

**New Relic で検知できること**:
- Database query count が異常に多い
- Similar SQL queries が複数回実行
- Database performance issues
- 修正版との比較で改善効果を確認

**確認手順**:
1. APM → Databases タブを開く
2. `/performance/n-plus-one` アクセス時のクエリ数を確認
3. Query details で同じパターンのクエリが複数あることを確認
4. 修正版 `/performance/n-plus-one-fixed` と比較
5. クエリ数が劇的に減少していることを確認

---

### 3. 📊 Core Web Vitals 問題

**エンドポイント**: `/performance/bad-vitals`

**問題内容**:
- **LCP (Largest Contentful Paint)**: 巨大な画像を遅延ロード（目標: 4秒以上）
- **INP (Interaction to Next Paint)**: 重い JavaScript 処理（目標: 500ms以上）
- **CLS (Cumulative Layout Shift)**: サイズ未指定の画像、遅延コンテンツ（目標: 0.25以上）

**New Relic Browser で検知できること**:
- Core Web Vitals スコアの劣化
- LCP, INP, CLS の各指標
- Session traces でユーザー体験を再現
- Page load time の内訳

**確認手順**:
1. Browser → Page views タブを開く
2. `/performance/bad-vitals` を選択
3. Core Web Vitals セクションで各指標を確認
4. Session traces でユーザー操作の詳細を確認
5. Timeline で何が遅いのかを分析

**注意**: Browser monitoring を有効化する必要があります（後述）。

---

### 4. 💾 メモリ大量使用

**エンドポイント**: `/performance/memory-intensive`

**問題内容**:
- 約 100MB のメモリを使用
- 大量のデータ構造を作成

**New Relic で検知できること**:
- High memory usage
- Memory consumption patterns
- Potential memory leaks

**確認手順**:
1. APM → JVMs (Memory) タブを開く
2. `/performance/memory-intensive` アクセス時のメモリ使用量を確認
3. Heap memory の変動を観察

---

### 5. 💥 エラー発生

**エンドポイント**:
- `/performance/error` (100% エラー)
- `/performance/random-error` (30% エラー)

**問題内容**:
- 意図的に例外を発生させる
- エラー率が高い

**New Relic で検知できること**:
- Error rate の上昇
- Exception details
- Stack traces
- Error patterns

**確認手順**:
1. APM → Errors タブを開く
2. `/performance/error` のエラー率を確認
3. Error details をクリックしてスタックトレースを確認
4. `/performance/random-error` の変動するエラー率を観察

---

### 6. ⚡ 高 CPU 使用

**エンドポイント**: `/performance/high-cpu`

**問題内容**:
- CPU 集約的な計算（1000万回のループ）
- フィボナッチ数列の計算

**New Relic で検知できること**:
- High CPU usage
- Long-running transactions
- CPU time vs. wall-clock time

**確認手順**:
1. APM → Transactions タブを開く
2. `/performance/high-cpu` の CPU time を確認
3. Top 5 transactions で比較

---

## New Relic での確認方法

### APM (Application Performance Monitoring)

#### 1. Overview
- 全体的なパフォーマンス状況
- Apdex score
- Throughput と Response time

#### 2. Transactions
- エンドポイント別のパフォーマンス
- 各トランザクションの詳細
- Slow transactions の特定

#### 3. Databases
- データベースクエリのパフォーマンス
- クエリ数と実行時間
- N+1 問題の検知

#### 4. Errors
- エラー率
- Exception details
- スタックトレース

### Browser Monitoring（要設定）

#### Core Web Vitals の測定

**Browser monitoring を有効化する方法**:

1. New Relic UI で Browser アプリケーションを作成
2. JavaScript スニペットを取得
3. `app/templates/base.html` の `<head>` タグ内に挿入:

```html
<head>
    <!-- 既存のコンテンツ -->

    <!-- New Relic Browser Monitoring -->
    <script type="text/javascript">
        // New Relic のスニペットをここに貼り付け
    </script>
</head>
```

## デモシナリオ例

### シナリオ 1: パフォーマンス劣化の検知

1. 通常のページ（`/products`）にアクセス
2. 遅いページ（`/performance/slow`）にアクセス
3. New Relic で両者のレスポンスタイムを比較
4. Apdex スコアの違いを確認

### シナリオ 2: N+1 問題の特定と修正

1. N+1 問題あり（`/performance/n-plus-one`）にアクセス
2. New Relic でデータベースクエリ数を確認（40+ クエリ）
3. 修正版（`/performance/n-plus-one-fixed`）にアクセス
4. クエリ数が 1-2 個に減少していることを確認
5. パフォーマンス改善効果を数値で確認

### シナリオ 3: エラー監視

1. エラーエンドポイント（`/performance/error`）にアクセス
2. New Relic でエラーが記録されることを確認
3. スタックトレースから原因を特定
4. Error rate が上昇していることを確認

## 負荷テスト

より多くのデータを生成するために、以下のコマンドで負荷をかけることができます：

```bash
# Apache Bench を使用
ab -n 100 -c 10 http://localhost:5001/performance/slow

# curl でループ
for i in {1..50}; do curl http://localhost:5001/performance/n-plus-one; done

# Python requests で負荷テスト
python -c "
import requests
for i in range(100):
    requests.get('http://localhost:5001/performance/slow')
    print(f'Request {i+1} completed')
"
```

## トラブルシューティング

### データが New Relic に表示されない

1. **ライセンスキーを確認**:
   ```bash
   docker-compose exec web env | grep NEW_RELIC
   ```

2. **アプリケーション名を確認**:
   ```bash
   docker-compose logs web | grep "App name"
   ```

3. **New Relic エージェントのログを確認**:
   ```bash
   docker-compose logs web | grep -i "new relic"
   ```

### Core Web Vitals が表示されない

- Browser monitoring が有効化されているか確認
- JavaScript スニペットが正しく挿入されているか確認
- リアルユーザーのアクセスが必要（Synthetic monitoring では測定されない）

## まとめ

| 問題の種類 | エンドポイント | 主な検知指標 |
|---------|------------|----------|
| 遅い処理 | `/performance/slow` | Transaction time, Apdex |
| N+1 問題 | `/performance/n-plus-one` | Query count, Similar queries |
| Core Web Vitals | `/performance/bad-vitals` | LCP, INP, CLS |
| メモリ | `/performance/memory-intensive` | Memory usage |
| エラー | `/performance/error` | Error rate, Stack traces |
| CPU | `/performance/high-cpu` | CPU time |

## 次のステップ

1. ✅ アプリケーションを起動
2. ✅ New Relic ライセンスキーを設定
3. ✅ 各エンドポイントにアクセス
4. ✅ New Relic UI で問題を確認
5. ⏭️ Browser monitoring を有効化（オプション）
6. ⏭️ アラート設定を追加
7. ⏭️ ダッシュボードをカスタマイズ

## 参考リンク

- [New Relic APM](https://docs.newrelic.com/docs/apm/)
- [Browser Monitoring](https://docs.newrelic.com/docs/browser/)
- [Core Web Vitals](https://docs.newrelic.com/docs/browser/new-relic-browser/browser-pro-features/core-web-vitals/)
