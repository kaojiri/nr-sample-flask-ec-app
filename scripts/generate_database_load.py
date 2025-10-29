#!/usr/bin/env python3
"""
PostgreSQLに意図的に負荷をかけるスクリプト
- 遅いクエリ
- ロック競合
- 同時接続負荷
を生成します
"""
import sys
import os
import time
import random
import threading
from concurrent.futures import ThreadPoolExecutor

# Add parent directory to path to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.product import Product
from sqlalchemy import text

def execute_slow_query():
    """意図的に遅いクエリを実行"""
    app = create_app()
    with app.app_context():
        print("🐌 遅いクエリを実行中...")
        try:
            # 1. CROSS JOINで大量の行を生成
            result = db.session.execute(text("""
                WITH RECURSIVE numbers AS (
                    SELECT 1 as n
                    UNION ALL
                    SELECT n + 1 FROM numbers WHERE n < 1000
                )
                SELECT 
                    n,
                    pg_sleep(0.001), -- 各行に1ミリ秒の遅延を追加
                    COUNT(*) OVER () as total_rows,
                    AVG(n) OVER (ORDER BY n ROWS BETWEEN 100 PRECEDING AND 100 FOLLOWING) as moving_avg
                FROM numbers
                ORDER BY n;
            """))
            print("   ✅ 遅いクエリ1完了")

            # 2. 意図的に非効率なクエリ（インデックスを使わない）
            result = db.session.execute(text("""
                SELECT 
                    u.email,
                    p.name as product_name,
                    o.created_at,
                    pg_sleep(0.002) -- 各行に2ミリ秒の遅延を追加
                FROM users u
                CROSS JOIN products p
                LEFT JOIN orders o ON u.id = o.user_id
                WHERE u.email LIKE '%@%'
                  AND CAST(p.price AS text) LIKE '%%'  -- インデックスを使わない条件
                ORDER BY random()
                LIMIT 100;
            """))
            print("   ✅ 遅いクエリ2完了")

        except Exception as e:
            print(f"   ❌ エラー: {e}")

def create_lock_contention():
    """ロック競合を生成"""
    app = create_app()
    with app.app_context():
        print("🔒 ロック競合を生成中...")
        try:
            # トランザクション1: 商品の在庫を更新
            def update_stock_1():
                with db.session.begin():
                    product = db.session.query(Product).first()
                    if product:
                        print(f"   トランザクション1: 商品 {product.name} の在庫を更新中...")
                        product.stock = product.stock - 1
                        time.sleep(2)  # 意図的に遅延を入れてロック競合を作る
                        db.session.commit()
                        print("   ✅ トランザクション1完了")

            # トランザクション2: 同じ商品の在庫を更新
            def update_stock_2():
                time.sleep(0.5)  # 少し待ってからロックを取得しに行く
                with db.session.begin():
                    product = db.session.query(Product).first()
                    if product:
                        print(f"   トランザクション2: 商品 {product.name} の在庫を更新中...")
                        product.stock = product.stock - 2
                        db.session.commit()
                        print("   ✅ トランザクション2完了")

            # 両方のトランザクションを同時に実行
            t1 = threading.Thread(target=update_stock_1)
            t2 = threading.Thread(target=update_stock_2)
            t1.start()
            t2.start()
            t1.join()
            t2.join()

        except Exception as e:
            print(f"   ❌ エラー: {e}")

def generate_concurrent_load():
    """同時接続による負荷を生成"""
    app = create_app()
    with app.app_context():
        print("🔄 同時接続負荷を生成中...")
        try:
            # 複数の同時クエリを実行
            def execute_query():
                # ランダムな待機を入れて複雑なクエリを実行
                db.session.execute(text(f"""
                    WITH RECURSIVE deep_tree AS (
                        SELECT 1 as level, CAST('Node1' AS VARCHAR) as path
                        UNION ALL
                        SELECT 
                            level + 1,
                            path || '->' || 'Node' || CAST(level + 1 AS VARCHAR)
                        FROM deep_tree
                        WHERE level < 5
                    ),
                    heavy_calc AS (
                        SELECT 
                            level,
                            path,
                            pg_sleep({random.uniform(0.1, 0.5)}) as wait_time
                        FROM deep_tree
                    )
                    SELECT * FROM heavy_calc;
                """))

            # 10個の同時接続を作成
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(execute_query) for _ in range(10)]
                for future in futures:
                    future.result()

            print("   ✅ 同時接続負荷生成完了")

        except Exception as e:
            print(f"   ❌ エラー: {e}")

def run_load_test(duration_seconds=300):  # 5分間実行
    """負荷テストを実行"""
    print("🚀 PostgreSQL高負荷テスト開始")
    print("=" * 60)
    print(f"実行時間: {duration_seconds}秒")
    print()

    start_time = time.time()
    iteration = 1

    try:
        while time.time() - start_time < duration_seconds:
            print(f"\n📍 イテレーション {iteration}")
            print("-" * 40)

            # 各種負荷を生成
            execute_slow_query()
            create_lock_contention()
            generate_concurrent_load()

            print(f"\n⏱️  経過時間: {int(time.time() - start_time)}秒")
            iteration += 1

            # 少し待機して次のイテレーションへ
            time.sleep(5)

    except KeyboardInterrupt:
        print("\n⚠️  ユーザーによりテストが中断されました")
    except Exception as e:
        print(f"\n❌ エラー: {e}")
    finally:
        print("\n✅ 負荷テスト完了")
        print("=" * 60)
        print("New Relicダッシュボードを確認してください:")
        print("1. Query Details: 遅いクエリが表示されるはずです")
        print("2. Wait Time Analysis: ロック待機時間が表示されるはずです")
        print("3. Database Connections: 同時接続数の増加が表示されるはずです")
        print("\n⏰ データの反映には数分かかる場合があります")

if __name__ == '__main__':
    run_load_test()