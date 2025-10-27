#!/usr/bin/env python3
"""
統合テスト: Main Application ↔ User Sync Service間の通信テスト
要件: 2.1, 2.2, 2.3, 2.4, 2.5
"""
import sys
import os
import unittest
import requests
import json
import time
from datetime import datetime
from unittest.mock import Mock, patch

# アプリケーションパスを追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

class TestMainAppUserSyncCommunication(unittest.TestCase):
    """Main Application ↔ User Sync Service間の通信テスト"""
    
    @classmethod
    def setUpClass(cls):
        """テストクラス初期化"""
        cls.main_app_url = "http://localhost:5000"
        cls.test_batch_id = None
        cls.created_users = []
        
    def setUp(self):
        """各テストの前処理"""
        # Main Applicationの接続確認
        try:
            response = requests.get(f"{self.main_app_url}/api/bulk-users/stats", timeout=5)
            if response.status_code != 200:
                self.skipTest("Main Applicationが利用できません")
        except requests.exceptions.ConnectionError:
            self.skipTest("Main Applicationに接続できません")
    
    def test_01_user_sync_service_initialization(self):
        """UserSyncServiceの初期化テスト (要件: 2.1)"""
        try:
            from app.services.user_sync_service import UserSyncService
            
            # UserSyncService初期化
            sync_service = UserSyncService("http://localhost:8080")
            
            # 基本属性確認
            self.assertIsNotNone(sync_service.load_tester_url)
            self.assertEqual(sync_service.load_tester_url, "http://localhost:8080")
            
            print("✓ UserSyncService初期化成功")
            
        except ImportError as e:
            self.fail(f"UserSyncServiceのインポートに失敗: {e}")
        except Exception as e:
            self.fail(f"UserSyncService初期化エラー: {e}")
    
    def test_02_bulk_user_creation_api(self):
        """一括ユーザー作成APIテスト (要件: 2.1)"""
        create_data = {
            "count": 3,
            "config": {
                "username_pattern": "integration_test_{id}@example.com",
                "password": "IntegrationTest123!",
                "email_domain": "example.com",
                "test_batch_id": f"integration_test_{int(time.time())}"
            }
        }
        
        response = requests.post(
            f"{self.main_app_url}/api/bulk-users/create",
            json=create_data,
            timeout=30
        )
        
        self.assertEqual(response.status_code, 201, f"一括ユーザー作成失敗: {response.text}")
        
        result = response.json()
        self.assertIn('batch_id', result)
        self.assertIn('successful_count', result)
        self.assertEqual(result['successful_count'], 3)
        
        # テスト用にバッチIDを保存
        self.__class__.test_batch_id = result['batch_id']
        self.__class__.created_users = result.get('created_users', [])
        
        print(f"✓ 一括ユーザー作成成功: バッチID={result['batch_id']}, 作成数={result['successful_count']}")
    
    def test_03_user_export_api(self):
        """ユーザーエクスポートAPIテスト (要件: 2.1, 2.2)"""
        # テストユーザーのみをエクスポート
        response = requests.get(
            f"{self.main_app_url}/api/bulk-users/export?test_users_only=true",
            timeout=15
        )
        
        self.assertEqual(response.status_code, 200, f"ユーザーエクスポート失敗: {response.text}")
        
        export_data = response.json()
        self.assertIn('users', export_data)
        self.assertIn('total_count', export_data)
        self.assertIn('export_timestamp', export_data)
        self.assertIn('source_system', export_data)
        
        # エクスポートされたユーザーの検証
        self.assertGreater(export_data['total_count'], 0, "エクスポートされたユーザーが0件です")
        
        # JSON形式の検証
        for user in export_data['users']:
            self.assertIn('username', user)
            self.assertIn('password', user)
            self.assertIn('is_test_user', user)
            self.assertTrue(user['is_test_user'], "テストユーザーフラグが正しくありません")
        
        print(f"✓ ユーザーエクスポート成功: {export_data['total_count']}件")
    
    def test_04_user_sync_service_export_functionality(self):
        """UserSyncServiceのエクスポート機能テスト (要件: 2.2)"""
        try:
            from app.services.user_sync_service import UserSyncService
            
            sync_service = UserSyncService("http://localhost:8080")
            
            # テストユーザーのみをエクスポート
            export_data = sync_service.export_users_from_app({"test_users_only": True})
            
            self.assertIsNotNone(export_data)
            self.assertGreater(len(export_data.users), 0, "エクスポートされたユーザーが0件です")
            
            # エクスポートデータの構造確認
            self.assertIsNotNone(export_data.export_timestamp)
            self.assertEqual(export_data.source_system, "main_application")
            self.assertEqual(export_data.total_count, len(export_data.users))
            
            # ユーザーデータの検証
            for user in export_data.users:
                self.assertIsNotNone(user.username)
                self.assertIsNotNone(user.password)
                self.assertTrue(user.is_test_user)
            
            print(f"✓ UserSyncServiceエクスポート成功: {len(export_data.users)}件")
            
        except Exception as e:
            self.fail(f"UserSyncServiceエクスポートエラー: {e}")
    
    def test_05_sync_status_api(self):
        """同期状況確認APIテスト (要件: 2.4)"""
        response = requests.get(
            f"{self.main_app_url}/api/bulk-users/sync/status",
            timeout=10
        )
        
        self.assertEqual(response.status_code, 200, f"同期状況確認失敗: {response.text}")
        
        sync_status = response.json()
        self.assertIn('total_checked', sync_status)
        self.assertIn('last_sync_check', sync_status)
        self.assertIn('sync_enabled', sync_status)
        
        print(f"✓ 同期状況確認成功: 検証数={sync_status.get('total_checked', 0)}")
    
    def test_06_user_sync_service_validation(self):
        """UserSyncServiceのデータ検証機能テスト (要件: 2.4)"""
        try:
            from app.services.user_sync_service import UserSyncService
            
            sync_service = UserSyncService("http://localhost:8080")
            
            # 検証機能テスト
            validation_result = sync_service.validate_sync_integrity()
            
            self.assertIsNotNone(validation_result)
            self.assertIn('is_valid', validation_result.__dict__)
            self.assertIn('total_checked', validation_result.__dict__)
            
            print(f"✓ UserSyncService検証成功: 検証数={validation_result.total_checked}")
            
        except Exception as e:
            self.fail(f"UserSyncService検証エラー: {e}")
    
    def test_07_error_handling_and_logging(self):
        """エラーハンドリングとログ機能テスト (要件: 2.5)"""
        # 無効なデータでの同期テスト
        invalid_sync_data = {
            "target": "invalid_target",
            "filter_criteria": {}
        }
        
        response = requests.post(
            f"{self.main_app_url}/api/bulk-users/sync",
            json=invalid_sync_data,
            timeout=15
        )
        
        # エラーレスポンスの確認（400または500系エラーを期待）
        self.assertIn(response.status_code, [400, 404, 500], 
                     f"無効なデータに対する適切なエラーレスポンスがありません: {response.status_code}")
        
        # エラーログの確認
        log_file = "logs/bulk_user_errors.log"
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8') as f:
                log_content = f.read()
            
            # 最近のエラーログが記録されているか確認
            self.assertIn("ERROR", log_content, "エラーログが記録されていません")
            print("✓ エラーログ記録確認")
        else:
            print("⚠ エラーログファイルが見つかりません")
        
        print("✓ エラーハンドリングテスト完了")
    
    @classmethod
    def tearDownClass(cls):
        """テストクラス終了処理"""
        # 作成したテストユーザーのクリーンアップ
        if cls.test_batch_id:
            try:
                response = requests.delete(
                    f"{cls.main_app_url}/api/bulk-users/batches/{cls.test_batch_id}",
                    timeout=10
                )
                if response.status_code == 200:
                    cleanup_result = response.json()
                    print(f"✓ テストデータクリーンアップ完了: 削除数={cleanup_result.get('deleted_count', 0)}")
                else:
                    print(f"⚠ テストデータクリーンアップ失敗: HTTP {response.status_code}")
            except Exception as e:
                print(f"⚠ テストデータクリーンアップエラー: {e}")


if __name__ == '__main__':
    # テスト実行
    unittest.main(verbosity=2)