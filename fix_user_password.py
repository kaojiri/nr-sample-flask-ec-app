#!/usr/bin/env python3
from app import create_app, db
from app.models import User

app = create_app()
with app.app_context():
    # 最初のテストユーザーのパスワードを修正
    user = User.query.filter_by(email='testuser_1761554998_0000@example.com').first()
    if user:
        print(f'Fixing password for user: {user.email}')
        user.set_password('TestPass123!')
        db.session.commit()
        
        # 確認
        if user.check_password('TestPass123!'):
            print('✅ Password fixed successfully!')
        else:
            print('❌ Password fix failed!')
    else:
        print('User not found')