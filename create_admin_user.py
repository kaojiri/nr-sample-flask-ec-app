#!/usr/bin/env python3
"""
Adminユーザーを作成するスクリプト
データベース初期化後にAdminユーザーが存在しない場合に使用
"""

from app import create_app, db
from app.models.user import User
import getpass
import sys

def create_admin_user():
    app = create_app()
    
    with app.app_context():
        # 既存のAdminユーザーをチェック
        existing_admin = User.query.filter_by(is_admin=True).first()
        if existing_admin:
            print(f"✅ Adminユーザーが既に存在します: {existing_admin.username}")
            return
        
        # Adminユーザーの情報を入力
        print("🔧 新しいAdminユーザーを作成します")
        username = input("ユーザー名を入力してください (デフォルト: admin): ").strip() or "admin"
        email = input("メールアドレスを入力してください (デフォルト: admin@example.com): ").strip() or "admin@example.com"
        
        # パスワードを安全に入力
        while True:
            password = getpass.getpass("パスワードを入力してください: ")
            if len(password) < 6:
                print("❌ パスワードは6文字以上である必要があります")
                continue
            
            password_confirm = getpass.getpass("パスワードを再入力してください: ")
            if password != password_confirm:
                print("❌ パスワードが一致しません")
                continue
            break
        
        # 既存のユーザー名・メールをチェック
        if User.query.filter_by(username=username).first():
            print(f"❌ ユーザー名 '{username}' は既に使用されています")
            return
        
        if User.query.filter_by(email=email).first():
            print(f"❌ メールアドレス '{email}' は既に使用されています")
            return
        
        # Adminユーザーを作成
        admin_user = User(
            username=username,
            email=email,
            is_admin=True
        )
        admin_user.set_password(password)
        
        try:
            db.session.add(admin_user)
            db.session.commit()
            print(f"✅ Adminユーザー '{username}' を作成しました")
            print(f"   メール: {email}")
            print(f"   Admin権限: True")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Adminユーザーの作成に失敗しました: {e}")
            sys.exit(1)

def list_users():
    """現在のユーザー一覧を表示"""
    app = create_app()
    
    with app.app_context():
        users = User.query.all()
        if not users:
            print("📝 ユーザーが存在しません")
            return
        
        print("📝 現在のユーザー一覧:")
        for user in users:
            admin_status = "👑 Admin" if user.is_admin else "👤 User"
            print(f"   {admin_status} | {user.username} ({user.email}) | ID: {user.id}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "list":
        list_users()
    else:
        create_admin_user()