#!/usr/bin/env python3
from app import create_app
from app.models import User

app = create_app()
with app.app_context():
    # 新しいバッチのユーザーを確認
    users = User.query.filter(User.email.like('testuser_1761557193_%')).all()
    print(f'Found {len(users)} new batch users')
    
    success_count = 0
    for user in users[:3]:  # 最初の3ユーザーをテスト
        print(f'\nUser: {user.email}')
        print(f'Username: {user.username}')
        
        # パスワードテスト
        if user.check_password('TestPass123!'):
            print('✅ Password check: SUCCESS')
            success_count += 1
        else:
            print('❌ Password check: FAILED')
            print(f'Password hash: {user.password_hash[:50]}...')
    
    print(f'\nSummary: {success_count}/{min(len(users), 3)} users have correct passwords')