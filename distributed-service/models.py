"""
分散サービス用のデータベースモデル
メインアプリケーションのモデルと完全に同等の構造
"""

from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def create_models(db):
    """データベースインスタンスを受け取ってモデルクラスを作成"""
    
    class User(db.Model):
        """ユーザーモデル - メインアプリケーションと同等"""
        __tablename__ = 'users'

        id = db.Column(db.Integer, primary_key=True)
        username = db.Column(db.String(80), unique=True, nullable=False)
        email = db.Column(db.String(120), unique=True, nullable=False)
        password_hash = db.Column(db.String(255), nullable=False)
        created_at = db.Column(db.DateTime, default=datetime.utcnow)
        
        # Bulk user management fields
        is_test_user = db.Column(db.Boolean, default=False, nullable=False)
        test_batch_id = db.Column(db.String(255), nullable=True)
        created_by_bulk = db.Column(db.Boolean, default=False, nullable=False)
        
        # Admin field
        is_admin = db.Column(db.Boolean, default=False, nullable=False)

        # Relationships
        orders = db.relationship('Order', backref='user', lazy=True)
        cart_items = db.relationship('CartItem', backref='user', lazy=True, cascade='all, delete-orphan')

        def __repr__(self):
            return f'<User {self.username}>'

    class Product(db.Model):
        """商品モデル - メインアプリケーションと同等"""
        __tablename__ = 'products'

        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String(200), nullable=False)
        description = db.Column(db.Text)
        price = db.Column(db.Numeric(10, 2), nullable=False)
        stock = db.Column(db.Integer, default=0)
        image_url = db.Column(db.String(500))
        category = db.Column(db.String(100))
        created_at = db.Column(db.DateTime, default=datetime.utcnow)
        updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

        # Relationships
        order_items = db.relationship('OrderItem', backref='product', lazy=True)
        cart_items = db.relationship('CartItem', backref='product', lazy=True)

        def __repr__(self):
            return f'<Product {self.name}>'

    class Order(db.Model):
        """注文モデル - メインアプリケーションと同等"""
        __tablename__ = 'orders'

        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
        total_amount = db.Column(db.Numeric(10, 2), nullable=False)
        status = db.Column(db.String(50), default='pending')  # pending, processing, shipped, delivered, cancelled
        created_at = db.Column(db.DateTime, default=datetime.utcnow)
        updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

        # Relationships
        items = db.relationship('OrderItem', backref='order', lazy=True, cascade='all, delete-orphan')

        def __repr__(self):
            return f'<Order {self.id}>'

    class OrderItem(db.Model):
        """注文アイテムモデル - メインアプリケーションと同等"""
        __tablename__ = 'order_items'

        id = db.Column(db.Integer, primary_key=True)
        order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
        product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
        quantity = db.Column(db.Integer, nullable=False)
        price = db.Column(db.Numeric(10, 2), nullable=False)

        def __repr__(self):
            return f'<OrderItem {self.id}>'

    class CartItem(db.Model):
        """カートアイテムモデル - メインアプリケーションと同等"""
        __tablename__ = 'cart_items'

        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
        product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
        quantity = db.Column(db.Integer, nullable=False, default=1)

        def __repr__(self):
            return f'<CartItem {self.id}>'

    return User, Product, Order, OrderItem, CartItem

def init_database(db):
    """データベースの初期化"""
    try:
        logger.info("データベースの初期化を開始します...")
        
        # テーブルの作成
        db.create_all()
        
        logger.info("データベースの初期化が完了しました")
        return True
        
    except Exception as e:
        logger.error(f"データベース初期化エラー: {e}")
        return False

def check_database_connection(db):
    """データベース接続の確認"""
    try:
        from sqlalchemy import text
        # 簡単なクエリでデータベース接続をテスト
        db.session.execute(text('SELECT 1'))
        db.session.commit()
        logger.info("データベース接続が正常です")
        return True
        
    except Exception as e:
        logger.error(f"データベース接続エラー: {e}")
        return False