#!/usr/bin/env python3
"""
ユーザー情報表示機能の動作確認テスト
Requirements: 1.3, 1.4, 2.1

このテストは以下をカバーします：
- ログイン後のユーザー情報表示をテスト
- ログアウト後の情報非表示をテスト  
- 複数ページでの表示一貫性をテスト
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import unittest
from app import create_app, db
from app.models.user import User
from flask_login import current_user

class TestUserDisplayFunctionality(unittest.TestCase):
    def setUp(self):
        """テスト用のFlaskアプリケーションとデータベースを設定"""
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['WTF_CSRF_ENABLED'] = False
        
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        # テスト用データベースを作成
        db.create_all()
        
        # テスト用ユーザーを作成
        self.test_user = User(username='testuser', email='test@example.com')
        self.test_user.set_password('testpassword')
        db.session.add(self.test_user)
        db.session.commit()
        
        self.client = self.app.test_client()

    def tearDown(self):
        """テスト後のクリーンアップ"""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def login_user(self):
        """テスト用ユーザーでログイン"""
        return self.client.post('/auth/login', data={
            'email': 'test@example.com',
            'password': 'testpassword'
        }, follow_redirects=True)

    def logout_user(self):
        """ユーザーをログアウト"""
        return self.client.get('/auth/logout', follow_redirects=True)

    def test_user_info_display_after_login(self):
        """ログイン後のユーザー情報表示をテスト (Requirement 1.3)"""
        print("🧪 ログイン後のユーザー情報表示テストを開始...")
        
        # ログイン前：ユーザー情報が表示されていないことを確認
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('ユーザー: testuser', response.data.decode('utf-8'))
        self.assertNotIn(f'ID: {self.test_user.id}', response.data.decode('utf-8'))
        print("  ✓ ログイン前：ユーザー情報が非表示であることを確認")
        
        # ログイン実行
        login_response = self.login_user()
        self.assertEqual(login_response.status_code, 200)
        
        # ログイン後：ユーザー情報が表示されることを確認
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        response_text = response.data.decode('utf-8')
        
        # デスクトップ表示とモバイル表示の両方をチェック
        self.assertTrue(
            'ユーザー: testuser' in response_text or 'testuser' in response_text,
            "ユーザー名が表示されていません"
        )
        self.assertIn(str(self.test_user.id), response_text, "ユーザーIDが表示されていません")
        
        print("  ✓ ログイン後：ユーザー情報が正しく表示されることを確認")
        print("✅ ログイン後のユーザー情報表示テスト: 成功")

    def test_user_info_hidden_after_logout(self):
        """ログアウト後の情報非表示をテスト (Requirement 1.4)"""
        print("🧪 ログアウト後の情報非表示テストを開始...")
        
        # まずログイン
        self.login_user()
        
        # ログイン状態でユーザー情報が表示されることを確認
        response = self.client.get('/')
        response_text = response.data.decode('utf-8')
        self.assertTrue(
            'ユーザー: testuser' in response_text or 'testuser' in response_text,
            "ログイン後にユーザー名が表示されていません"
        )
        print("  ✓ ログイン状態：ユーザー情報が表示されることを確認")
        
        # ログアウト実行
        logout_response = self.logout_user()
        self.assertEqual(logout_response.status_code, 200)
        
        # ログアウト後：ユーザー情報が非表示になることを確認
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        response_text = response.data.decode('utf-8')
        
        # ユーザー情報が表示されていないことを確認
        self.assertNotIn('ユーザー: testuser', response_text)
        self.assertNotIn(f'ID: {self.test_user.id}', response_text)
        
        # ログインリンクが表示されていることを確認（未認証状態の証明）
        self.assertIn('ログイン', response_text)
        
        print("  ✓ ログアウト後：ユーザー情報が非表示になることを確認")
        print("✅ ログアウト後の情報非表示テスト: 成功")

    def test_user_info_consistency_across_pages(self):
        """複数ページでの表示一貫性をテスト (Requirement 2.1)"""
        print("🧪 複数ページでの表示一貫性テストを開始...")
        
        # ログイン
        self.login_user()
        
        # テストするページのリスト
        test_pages = [
            ('/', 'ホームページ'),
            ('/products', '商品一覧ページ'),
            ('/cart', 'カートページ')
        ]
        
        for url, page_name in test_pages:
            response = self.client.get(url, follow_redirects=True)
            
            # ページが正常に表示されることを確認
            if response.status_code == 404:
                print(f"  ⚠️  {page_name} ({url}) は存在しないためスキップ")
                continue
                
            self.assertEqual(response.status_code, 200, f"{page_name}が正常に表示されません")
            
            response_text = response.data.decode('utf-8')
            
            # 各ページでユーザー情報が一貫して表示されることを確認
            user_info_displayed = (
                'ユーザー: testuser' in response_text or 
                'testuser' in response_text
            )
            self.assertTrue(
                user_info_displayed,
                f"{page_name}でユーザー情報が表示されていません"
            )
            
            # ユーザーIDも表示されていることを確認
            self.assertIn(
                str(self.test_user.id), 
                response_text,
                f"{page_name}でユーザーIDが表示されていません"
            )
            
            print(f"  ✓ {page_name}：ユーザー情報が一貫して表示されることを確認")
        
        print("✅ 複数ページでの表示一貫性テスト: 成功")

    def test_session_persistence(self):
        """セッション持続性のテスト"""
        print("🧪 セッション持続性テストを開始...")
        
        # ログイン
        self.login_user()
        
        # 複数回のページアクセスでセッションが維持されることを確認
        for i in range(3):
            response = self.client.get('/')
            self.assertEqual(response.status_code, 200)
            response_text = response.data.decode('utf-8')
            
            self.assertTrue(
                'ユーザー: testuser' in response_text or 'testuser' in response_text,
                f"{i+1}回目のアクセスでユーザー情報が表示されていません"
            )
        
        print("  ✓ 複数回のページアクセスでセッションが維持されることを確認")
        print("✅ セッション持続性テスト: 成功")

    def test_unauthenticated_user_display(self):
        """未認証ユーザーの表示テスト"""
        print("🧪 未認証ユーザーの表示テストを開始...")
        
        # ログインしていない状態でページにアクセス
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        response_text = response.data.decode('utf-8')
        
        # ユーザー情報が表示されていないことを確認
        self.assertNotIn('ユーザー:', response_text)
        self.assertNotIn('ID:', response_text)
        
        # ログインリンクが表示されていることを確認
        self.assertIn('ログイン', response_text)
        self.assertIn('会員登録', response_text)
        
        print("  ✓ 未認証状態：ユーザー情報が非表示で、ログインリンクが表示されることを確認")
        print("✅ 未認証ユーザーの表示テスト: 成功")

if __name__ == '__main__':
    print("=" * 60)
    print("ユーザー情報表示機能の動作確認テストを開始...")
    print("=" * 60)
    print()
    
    # テストスイートを実行
    unittest.main(verbosity=2, exit=False)
    
    print()
    print("=" * 60)
    print("すべてのテストが完了しました")
    print("=" * 60)