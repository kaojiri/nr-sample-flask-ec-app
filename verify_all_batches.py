#!/usr/bin/env python3
from app import create_app
from app.models import User

app = create_app()
with app.app_context():
    # 各バッチのパスワードを確認
    test_patterns = [
        ('test1_1761562375_%', '1ユーザー'),
        ('test5_1761562399_%', '5ユーザー'),
        ('test10_1761562423_%', '10ユーザー')
    ]
    
    total_success = 0
    total_users = 0
    
    for pattern, description in test_patterns:
        users = User.query.filter(User.email.like(pattern)).all()
        success_count = 0
        
        print(f'\n=== {description}バッチ ===')
        print(f'Found {len(users)} users')
        
        for user in users:
            if user.check_password('TestPass123!'):
                success_count += 1
            else:
                print(f'❌ Password failed: {user.email}')
        
        print(f'Password success: {success_count}/{len(users)}')
        
        if success_count == len(users) and len(users) > 0:
            print('✅ All passwords correct!')
        elif len(users) == 0:
            print('⚠️ No users found')
        else:
            print('❌ Some passwords incorrect')
        
        total_success += success_count
        total_users += len(users)
    
    print(f'\n=== 総合結果 ===')
    print(f'Total: {total_success}/{total_users} users with correct passwords')
    
    if total_success == total_users and total_users > 0:
        print('🎉 全ての人数パターンでパスワード設定が成功！')
    else:
        print('❌ 一部でパスワード設定に問題があります')