#!/usr/bin/env python3
from app import create_app, db
from app.models import User

app = create_app()
with app.app_context():
    # 全てのテストユーザーのパスワードを修正
    users = User.query.filter(User.email.like('testuser_1761554998_%')).all()
    print(f'Found {len(users)} users to fix')
    
    fixed_count = 0
    for user in users:
        print(f'Fixing password for user: {user.email}')
        user.set_password('TestPass123!')
        fixed_count += 1
    
    db.session.commit()
    print(f'✅ Fixed passwords for {fixed_count} users')
    
    # 確認
    print('\nVerifying passwords:')
    for user in users:
        if user.check_password('TestPass123!'):
            print(f'✅ {user.email}: OK')
        else:
            print(f'❌ {user.email}: FAILED')