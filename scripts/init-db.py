#!/usr/bin/env python3
"""
Database initialization script
Creates sample products for the EC application
"""

import sys
import os

# Add parent directory to path to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Product, User

def init_db():
    app = create_app()

    with app.app_context():
        # Create all tables
        print("Creating database tables...")
        db.create_all()

        # Check if products already exist
        if Product.query.first():
            print("Database already initialized.")
            return

        # Create sample products
        print("Creating sample products...")

        sample_products = [
            {
                'name': 'ノートパソコン',
                'description': '高性能なノートパソコン。ビジネスにも最適です。',
                'price': 89800,
                'stock': 10,
                'category': 'electronics',
                'image_url': 'https://via.placeholder.com/300x300?text=Laptop'
            },
            {
                'name': 'ワイヤレスマウス',
                'description': '快適な操作性のワイヤレスマウス',
                'price': 2980,
                'stock': 50,
                'category': 'electronics',
                'image_url': 'https://via.placeholder.com/300x300?text=Mouse'
            },
            {
                'name': 'メカニカルキーボード',
                'description': 'ゲーミングにも最適なメカニカルキーボード',
                'price': 12800,
                'stock': 30,
                'category': 'electronics',
                'image_url': 'https://via.placeholder.com/300x300?text=Keyboard'
            },
            {
                'name': 'USB-C ハブ',
                'description': '7-in-1 USB-C ハブ。HDMI、USB3.0対応',
                'price': 4980,
                'stock': 40,
                'category': 'electronics',
                'image_url': 'https://via.placeholder.com/300x300?text=USB-C+Hub'
            },
            {
                'name': 'ワイヤレスイヤホン',
                'description': 'ノイズキャンセリング機能付きワイヤレスイヤホン',
                'price': 15800,
                'stock': 25,
                'category': 'electronics',
                'image_url': 'https://via.placeholder.com/300x300?text=Earbuds'
            },
            {
                'name': 'モバイルバッテリー',
                'description': '20000mAh 大容量モバイルバッテリー',
                'price': 3980,
                'stock': 60,
                'category': 'electronics',
                'image_url': 'https://via.placeholder.com/300x300?text=Power+Bank'
            },
            {
                'name': 'スマートウォッチ',
                'description': '健康管理機能付きスマートウォッチ',
                'price': 24800,
                'stock': 15,
                'category': 'electronics',
                'image_url': 'https://via.placeholder.com/300x300?text=Smart+Watch'
            },
            {
                'name': 'Webカメラ',
                'description': 'フルHD対応Webカメラ。リモートワークに最適',
                'price': 5980,
                'stock': 35,
                'category': 'electronics',
                'image_url': 'https://via.placeholder.com/300x300?text=Webcam'
            },
            {
                'name': 'モニターアーム',
                'description': 'デュアルモニター対応アーム',
                'price': 8980,
                'stock': 20,
                'category': 'electronics',
                'image_url': 'https://via.placeholder.com/300x300?text=Monitor+Arm'
            },
            {
                'name': 'ゲーミングヘッドセット',
                'description': '7.1chサラウンド対応ゲーミングヘッドセット',
                'price': 9800,
                'stock': 28,
                'category': 'electronics',
                'image_url': 'https://via.placeholder.com/300x300?text=Headset'
            },
            {
                'name': 'SSD 1TB',
                'description': 'NVMe M.2 SSD 1TB 高速ストレージ',
                'price': 11800,
                'stock': 45,
                'category': 'electronics',
                'image_url': 'https://via.placeholder.com/300x300?text=SSD'
            },
            {
                'name': 'グラフィックタブレット',
                'description': 'デジタルイラスト制作用タブレット',
                'price': 19800,
                'stock': 12,
                'category': 'electronics',
                'image_url': 'https://via.placeholder.com/300x300?text=Tablet'
            }
        ]

        for product_data in sample_products:
            product = Product(**product_data)
            db.session.add(product)

        # Create a test user
        print("Creating test user...")
        test_user = User(username='testuser', email='test@example.com')
        test_user.set_password('password123')
        db.session.add(test_user)

        db.session.commit()
        print(f"Successfully created {len(sample_products)} products and 1 test user")
        print("\nTest user credentials:")
        print("Email: test@example.com")
        print("Password: password123")
        


if __name__ == '__main__':
    init_db()
