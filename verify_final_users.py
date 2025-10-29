#!/usr/bin/env python3
from app import create_app
from app.models import User

app = create_app()
with app.app_context():
    # 最終修正後に作成されたユーザーを確認
    users = User.query.filter(User.email.like('testuser_1761556841_%')).all()
    print(f'Found {len(users)} final users')
    
    for user in users:
        print(f'\nUser: {user.email}')
        print(f'Username: {user.username}')
        
        # パスワードテスト
        if user.check_password('TestPass123!'):
            print('✅ Password check: SUCCESS')
        else:
            print('❌ Password check: FAILED')
            print(f'Password hash: {user.password_hash[:50]}...')