#!/usr/bin/env python3
from app import create_app, db
from app.models import User
from werkzeug.security import generate_password_hash, check_password_hash

app = create_app()
with app.app_context():
    # 手動でユーザーを作成してテスト
    print("Creating test user manually...")
    
    # 1. 直接password_hashを設定
    user1 = User(
        username="debug_user1@example.com",
        email="debug_user1@example.com",
        password_hash=generate_password_hash("TestPass123!"),
        is_test_user=True,
        test_batch_id="debug_batch",
        created_by_bulk=True
    )
    
    # 2. set_passwordメソッドを使用
    user2 = User(
        username="debug_user2@example.com",
        email="debug_user2@example.com",
        is_test_user=True,
        test_batch_id="debug_batch",
        created_by_bulk=True
    )
    user2.set_password("TestPass123!")
    
    db.session.add(user1)
    db.session.add(user2)
    db.session.commit()
    
    print("Testing passwords...")
    
    # パスワードテスト
    print(f"User1 (direct hash): {user1.check_password('TestPass123!')}")
    print(f"User2 (set_password): {user2.check_password('TestPass123!')}")
    
    # ハッシュを比較
    print(f"User1 hash: {user1.password_hash[:50]}...")
    print(f"User2 hash: {user2.password_hash[:50]}...")
    
    # 手動でハッシュを生成してテスト
    manual_hash = generate_password_hash("TestPass123!")
    print(f"Manual hash: {manual_hash[:50]}...")
    print(f"Manual hash check: {check_password_hash(manual_hash, 'TestPass123!')}")
    
    # クリーンアップ
    db.session.delete(user1)
    db.session.delete(user2)
    db.session.commit()
    print("Cleanup completed")