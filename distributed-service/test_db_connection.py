#!/usr/bin/env python3
"""
分散サービスのデータベース接続テストスクリプト
"""

import os
import sys
import logging
from app import app, db
from models import create_models, check_database_connection, init_database

# モデルクラスを作成
User, Product, Order, OrderItem, CartItem = create_models(db)

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_database_connection():
    """データベース接続のテスト"""
    logger.info("データベース接続テストを開始します...")
    
    with app.app_context():
        # 基本的な接続テスト
        if check_database_connection(db):
            logger.info("✓ データベース接続が正常です")
        else:
            logger.error("✗ データベース接続に失敗しました")
            return False
        
        # テーブル存在確認
        try:
            # 各モデルのテーブルが存在するかチェック
            models = [User, Product, Order, OrderItem, CartItem]
            for model in models:
                count = model.query.count()
                logger.info(f"✓ {model.__tablename__} テーブル: {count} レコード")
        except Exception as e:
            logger.warning(f"テーブル確認エラー (テーブルが存在しない可能性): {e}")
            logger.info("データベース初期化を実行します...")
            if init_database(db):
                logger.info("✓ データベース初期化が完了しました")
                # 再度テーブル確認
                for model in models:
                    count = model.query.count()
                    logger.info(f"✓ {model.__tablename__} テーブル: {count} レコード")
            else:
                logger.error("✗ データベース初期化に失敗しました")
                return False
        
        return True

def test_model_operations():
    """基本的なモデル操作のテスト"""
    logger.info("モデル操作テストを開始します...")
    
    with app.app_context():
        try:
            # テストユーザーの作成
            test_user = User(
                username='test_distributed_user',
                email='test@distributed.com',
                password_hash='test_hash'
            )
            
            # テスト商品の作成
            test_product = Product(
                name='Test Product',
                description='Test Description',
                price=100.00,
                category='Test Category',
                stock=10
            )
            
            # データベースに追加
            db.session.add(test_user)
            db.session.add(test_product)
            db.session.commit()
            
            logger.info("✓ テストデータの作成が成功しました")
            
            # データの確認
            user_count = User.query.filter_by(username='test_distributed_user').count()
            product_count = Product.query.filter_by(name='Test Product').count()
            
            logger.info(f"✓ テストユーザー数: {user_count}")
            logger.info(f"✓ テスト商品数: {product_count}")
            
            # テストデータのクリーンアップ
            User.query.filter_by(username='test_distributed_user').delete()
            Product.query.filter_by(name='Test Product').delete()
            db.session.commit()
            
            logger.info("✓ テストデータのクリーンアップが完了しました")
            return True
            
        except Exception as e:
            logger.error(f"✗ モデル操作テストエラー: {e}")
            db.session.rollback()
            return False

def main():
    """メイン関数"""
    logger.info("=== 分散サービス データベーステスト ===")
    
    # データベース接続テスト
    if not test_database_connection():
        logger.error("データベース接続テストに失敗しました")
        sys.exit(1)
    
    # モデル操作テスト
    if not test_model_operations():
        logger.error("モデル操作テストに失敗しました")
        sys.exit(1)
    
    logger.info("=== 全てのテストが成功しました ===")

if __name__ == "__main__":
    main()