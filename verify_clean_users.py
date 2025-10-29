#!/usr/bin/env python3
from app import create_app
from app.models import User

app = create_app()
with app.app_context():
    # 新しく作成されたユーザーを確認
    users = User.query.filter(User.email.like('testuser_1761558456_%')).all()
    print(f'Found {len(users)} clean users')
    
    success_count = 0
    for user in users:
        print(f'\nUser: {user.email}')
        print(f'Username: {user.username}')
        print(f'Email == Username: {user.email == user.username}')
        
        # パスワードテスト
        if user.check_password('TestPass123!'):
            print('✅ Password check: SUCCESS')
            success_count += 1
        else:
            print('❌ Password check: FAILED')
    
    print(f'\nSummary: {success_count}/{len(users)} users have correct passwords')