#!/usr/bin/env python3
"""
分散サービス用のデータベース管理スクリプト
マイグレーションとデータベース初期化を管理
"""

import os
import sys
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate, init, migrate, upgrade, downgrade

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app():
    """アプリケーションファクトリ"""
    app = Flask(__name__)
    
    # データベース設定
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL', 
        'postgresql://postgres:postgres@postgres:5432/ecdb'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    return app

def setup_database(app):
    """データベースとマイグレーションの設定"""
    db = SQLAlchemy(app)
    migrate = Migrate(app, db)
    
    # モデルをインポート（マイグレーション検出のため）
    from models import User, Product, Order, OrderItem, CartItem
    
    return db, migrate

def init_migrations():
    """マイグレーションの初期化"""
    try:
        logger.info("マイグレーションの初期化を開始します...")
        init()
        logger.info("マイグレーションの初期化が完了しました")
        return True
    except Exception as e:
        logger.error(f"マイグレーション初期化エラー: {e}")
        return False

def create_migration(message="Auto migration"):
    """新しいマイグレーションファイルの作成"""
    try:
        logger.info(f"マイグレーションファイルを作成します: {message}")
        migrate(message=message)
        logger.info("マイグレーションファイルの作成が完了しました")
        return True
    except Exception as e:
        logger.error(f"マイグレーション作成エラー: {e}")
        return False

def apply_migrations():
    """マイグレーションの適用"""
    try:
        logger.info("マイグレーションを適用します...")
        upgrade()
        logger.info("マイグレーションの適用が完了しました")
        return True
    except Exception as e:
        logger.error(f"マイグレーション適用エラー: {e}")
        return False

def rollback_migration():
    """マイグレーションのロールバック"""
    try:
        logger.info("マイグレーションをロールバックします...")
        downgrade()
        logger.info("マイグレーションのロールバックが完了しました")
        return True
    except Exception as e:
        logger.error(f"マイグレーションロールバックエラー: {e}")
        return False

def main():
    """メイン関数"""
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python manage_db.py init          - マイグレーション初期化")
        print("  python manage_db.py migrate       - マイグレーション作成")
        print("  python manage_db.py upgrade       - マイグレーション適用")
        print("  python manage_db.py downgrade     - マイグレーションロールバック")
        return
    
    command = sys.argv[1]
    
    # アプリケーションコンテキストで実行
    app = create_app()
    with app.app_context():
        db, migrate_instance = setup_database(app)
        
        if command == "init":
            init_migrations()
        elif command == "migrate":
            message = sys.argv[2] if len(sys.argv) > 2 else "Auto migration"
            create_migration(message)
        elif command == "upgrade":
            apply_migrations()
        elif command == "downgrade":
            rollback_migration()
        else:
            print(f"不明なコマンド: {command}")

if __name__ == "__main__":
    main()