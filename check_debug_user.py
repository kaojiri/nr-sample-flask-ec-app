#!/usr/bin/env python3
from app import create_app
from app.models import User

app = create_app()
with app.app_context():
    # デバッグユーザーを確認
    user = User.query.get(122)
    if user:
        print(f'Debug User (ID: 122):')
        print(f'  Email: {user.email}')
        print(f'  Username: {user.username}')
        print(f'  Password check with TestPass123!: {user.check_password("TestPass123!")}')
        print(f'  Password hash: {user.password_hash[:50]}...')
    else:
        print('Debug user not found')