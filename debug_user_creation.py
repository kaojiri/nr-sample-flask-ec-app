#!/usr/bin/env python3
from app import create_app, db
from app.services.bulk_user_creator import BulkUserCreator, UserCreationConfig

app = create_app()
with app.app_context():
    print("=== デバッグ: ユーザー作成プロセス ===")
    
    # 設定を作成
    config = UserCreationConfig(
        username_pattern="debug_{id}@example.com",
        password="TestPass123!",
        email_domain="example.com",
        batch_size=1,
        max_users_per_batch=1,
        user_role="user"
    )
    
    print(f"設定パスワード: {config.password}")
    
    # BulkUserCreatorを初期化
    creator = BulkUserCreator()
    
    # 認証情報を生成
    credentials = creator.generate_unique_credentials(1, config)
    
    if credentials:
        cred = credentials[0]
        print(f"生成された認証情報:")
        print(f"  Username: {cred.username}")
        print(f"  Email: {cred.email}")
        print(f"  Password: {cred.password}")
        print(f"  Password == Config: {cred.password == config.password}")
    else:
        print("認証情報の生成に失敗")