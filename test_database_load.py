#!/usr/bin/env python3
"""
PostgreSQL負荷テスト用スクリプト
New RelicのQuery detailsとWait time Analysisにデータを表示させるため
"""

import sys
import os
import time
import threading
import random
from concurrent.futures import ThreadPoolExecutor

# Add parent directory to path to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from app import create_app, db
from app.models.user import User
from app.models.product import Product
from app.models.order import Order

def create_slow_queries():
    """遅いクエリを意図的に実行"""
    app = create_app()
    
    with app.app_context():
        print("🐌 遅いクエリを実行中...")
        
        # 1. 大きなテーブルスキャン（インデックスを使わない）
        from sqlalchemy import text
        result = db.session.execute(text("""
            SELECT u.*, p.*, COUNT(o.id) as order_count
            FROM users u
            CROSS JOIN products p
            LEFT JOIN orders o ON u.id = o.user_id
            WHERE u.email LIKE '%@%'
            GROUP BY u.id, p.id
            ORDER BY random()
            LIMIT 100;
        """))
        print(f"   大きなテーブルスキャン完了: {len(list(result))} 件")
        
        # 2. 複雑な集計クエリ
        result = db.session.execute(text("""
            WITH user_stats AS (
                SELECT 
                    u.id,
                    u.username,
                    COUNT(o.id) as total_orders,
                    COALESCE(SUM(oi.quantity * p.price), 0) as total_spent
                FROM users u
                LEFT JOIN orders o ON u.id = o.user_id
                LEFT JOIN order_items oi ON o.id = oi.order_id
                LEFT JOIN products p ON oi.product_id = p.id
                GROUP BY u.id, u.username
            )
            SELECT 
                us.*,
                CASE 
                    WHEN us.total_spent > 1000 THEN 'VIP'
                    WHEN us.total_spent > 500 THEN 'Premium'
                    ELSE 'Regular'
                END as customer_tier
            FROM user_stats us
            ORDER BY us.total_spent DESC;
        """))
        print(f"   複雑な集計クエリ完了: {len(list(result))} 件")
        
        # 3. 意図的に遅いクエリ（pg_sleep使用）
        db.session.execute(text("SELECT pg_sleep(2);"))
        print("   意図的な遅延クエリ完了: 2秒待機")

def create_concurrent_load():
    """同時接続による負荷を生成"""
    app = create_app()
    
    with app.app_context():
        print("🔄 同時接続負荷を生成中...")
        
        # ランダムなユーザー検索
        user_id = random.randint(1, 10)
        user = db.session.get(User, user_id)
        if user:
            # ユーザーの注文履歴を取得
            orders = Order.query.filter_by(user_id=user.id).all()
            print(f"   ユーザー {user.username} の注文: {len(orders)} 件")
        
        # ランダムな商品検索
        products = Product.query.filter(Product.price > random.randint(10, 100)).limit(5).all()
        print(f"   商品検索結果: {len(products)} 件")
        
        # データベース統計情報を更新
        db.session.execute(text("ANALYZE;"))
        print("   統計情報更新完了")

def create_lock_contention():
    """ロック競合を生成"""
    app = create_app()
    
    with app.app_context():
        print("🔒 ロック競合を生成中...")
        
        try:
            # トランザクション開始
            db.session.begin()
            
            # 商品の在庫を更新（ロックを取得）
            product = Product.query.first()
            if product:
                original_stock = product.stock
                product.stock = product.stock - 1
                print(f"   商品 {product.name} の在庫を更新: {original_stock} -> {product.stock}")
                
                # 少し待機（他のスレッドがロック待ちになるように）
                time.sleep(1)
                
                db.session.commit()
                print("   トランザクション完了")
        except Exception as e:
            db.session.rollback()
            print(f"   エラー: {e}")

def run_load_test():
    """負荷テストを実行"""
    print("🚀 PostgreSQL負荷テスト開始")
    print("=" * 50)
    
    # 複数スレッドで同時実行
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        
        # 遅いクエリを実行
        futures.append(executor.submit(create_slow_queries))
        
        # 同時接続負荷を複数スレッドで実行
        for i in range(3):
            futures.append(executor.submit(create_concurrent_load))
        
        # ロック競合を生成
        futures.append(executor.submit(create_lock_contention))
        
        # すべてのタスクの完了を待機
        for future in futures:
            try:
                future.result()
            except Exception as e:
                print(f"エラー: {e}")
    
    print("=" * 50)
    print("✅ 負荷テスト完了")
    print()
    print("📊 New Relicダッシュボードを確認してください:")
    print("   - Query details: 遅いクエリが表示されるはずです")
    print("   - Wait time Analysis: ロック待機時間が表示されるはずです")
    print("   - Database connections: 同時接続数の増加が表示されるはずです")
    print()
    print("⏰ データの反映には数分かかる場合があります")

if __name__ == '__main__':
    run_load_test()