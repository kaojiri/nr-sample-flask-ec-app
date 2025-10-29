#!/usr/bin/env python3
from app import create_app
from app.models import User

app = create_app()
with app.app_context():
    # 最新の一括作成ユーザーを取得
    users = User.query.filter(User.email.like('testuser_1761554998_%')).all()
    print(f'Found {len(users)} users')
    
    if users:
        user = users[0]
        print(f'User: {user.email}')
        print(f'Username: {user.username}')
        print(f'Is test user: {user.is_test_user}')
        print(f'Test batch ID: {user.test_batch_id}')
        print(f'Created by bulk: {getattr(user, "created_by_bulk", "N/A")}')
        
        # 様々なパスワードでテスト
        test_passwords = [
            'TestPass123!',
            'password123',
            'testpass',
            user.username,  # ユーザー名と同じ
            'defaultpass'
        ]
        
        print('\nPassword tests:')
        for pwd in test_passwords:
            result = user.check_password(pwd)
            print(f'  {pwd}: {result}')