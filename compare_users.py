#!/usr/bin/env python3
from app import create_app
from app.models import User

app = create_app()
with app.app_context():
    # 以前成功していたユーザー（修正したもの）
    old_users = User.query.filter(User.email.like('testuser_1761554998_%')).all()
    print('=== 以前成功していたユーザー ===')
    for user in old_users[:2]:
        print(f'Email: {user.email}')
        print(f'Username: {user.username}')
        print(f'Password check: {user.check_password("TestPass123!")}')
        print()
    
    # 現在のユーザー
    new_users = User.query.filter(User.email.like('testuser_1761557665_%')).all()
    print('=== 現在のユーザー ===')
    for user in new_users[:2]:
        print(f'Email: {user.email}')
        print(f'Username: {user.username}')
        print(f'Password check: {user.check_password("TestPass123!")}')
        print()