#!/usr/bin/env python3
"""
ユーザー情報表示の安全性テスト
テンプレートでのNone値処理とXSS対策を確認
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models.user import User
from flask import render_template_string
import unittest
from unittest.mock import Mock

class TestUserDisplaySafety(unittest.TestCase):
    def setUp(self):
        """テスト用のFlaskアプリケーションを設定"""
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        """テスト後のクリーンアップ"""
        self.app_context.pop()

    def test_none_value_handling(self):
        """None値の安全な処理をテスト"""
        # モックユーザーオブジェクトを作成（None値を含む）
        mock_user = Mock()
        mock_user.is_authenticated = True
        mock_user.username = None
        mock_user.id = None
        
        # テンプレート文字列（実際のbase.htmlから抜粋）
        template_str = """
        {% if current_user.is_authenticated %}
            ユーザー: {{ current_user.username|default('不明', true)|e }} (ID: {{ current_user.id|default('N/A', true)|e }})
        {% endif %}
        """
        
        with self.app.test_request_context():
            # テンプレートをレンダリング
            result = render_template_string(template_str, current_user=mock_user)
            
            # デフォルト値が正しく表示されることを確認
            self.assertIn('ユーザー: 不明', result)
            self.assertIn('ID: N/A', result)
            print("✓ None値のデフォルト表示テスト: 成功")

    def test_xss_protection(self):
        """XSS攻撃に対する保護をテスト"""
        # 悪意のあるスクリプトを含むモックユーザー
        mock_user = Mock()
        mock_user.is_authenticated = True
        mock_user.username = "<script>alert('XSS')</script>"
        mock_user.id = "<img src=x onerror=alert('XSS')>"
        
        template_str = """
        {% if current_user.is_authenticated %}
            ユーザー: {{ current_user.username|default('不明', true)|e }} (ID: {{ current_user.id|default('N/A', true)|e }})
        {% endif %}
        """
        
        with self.app.test_request_context():
            result = render_template_string(template_str, current_user=mock_user)
            
            # スクリプトタグがエスケープされていることを確認
            self.assertNotIn('<script>', result)
            self.assertNotIn('<img', result)
            self.assertIn('&lt;script&gt;', result)
            self.assertIn('&lt;img', result)
            print("✓ XSS保護テスト: 成功")

    def test_normal_user_display(self):
        """正常なユーザー情報の表示をテスト"""
        mock_user = Mock()
        mock_user.is_authenticated = True
        mock_user.username = "testuser"
        mock_user.id = 123
        
        template_str = """
        {% if current_user.is_authenticated %}
            ユーザー: {{ current_user.username|default('不明', true)|e }} (ID: {{ current_user.id|default('N/A', true)|e }})
        {% endif %}
        """
        
        with self.app.test_request_context():
            result = render_template_string(template_str, current_user=mock_user)
            
            # 正常な値が表示されることを確認
            self.assertIn('ユーザー: testuser', result)
            self.assertIn('ID: 123', result)
            print("✓ 正常なユーザー情報表示テスト: 成功")

if __name__ == '__main__':
    print("ユーザー情報表示の安全性テストを開始...")
    unittest.main(verbosity=2)