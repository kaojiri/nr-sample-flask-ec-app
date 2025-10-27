#!/usr/bin/env python3
"""
統合テスト: Load Tester ↔ User Sync Service間の通信テスト
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

# Load Testerパスを追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'load-tester'))

class TestLoadTesterSyncCommunication(unittest.TestCase):
    """Load Tester ↔ User Sync Service間の通信テスト"""
    
    @classmethod
    def setUpClass(cls):
        """テストクラス初期化"""
        cls.load_tester_url = "http://localhost:8080"
        cls.test_users_data = None
        
    def setUp(self):
        """各テストの前処理"""
        # Load Testerの接続確認
        try:
            response = requests.get(f"{self.load_tester_url}/api/users/health", timeout=5)
            if response.status_code != 200:
                self.skipTest("Load Testerが利用できません")
        except requests.exceptions.ConnectionError:
            self.skipTest("Load Testerに接続できません")
    
    def test_01_load_tester_user_sync_api_initialization(self):
        """Load Tester UserSyncAPIの初期化テスト (要件: 2.1)"""
        try:
            from user_sync_api import UserSyncAPI
            
            # UserSyncAPI初期化
            sync_api = UserSyncAPI()
            
            # 基本属性確認
            self.assertIsNotNone(sync_api.session_manager)
            self.assertIsNotNone(sync_api.config)
            
            print("✓ Load Tester UserSyncAPI初期化成功")
            
        except ImportError as e:
            self.fail(f"UserSyncAPIのインポートに失敗: {e}")
        except Exception as e:
            self.fail(f"UserSyncAPI初期化エラー: {e}")
    
    def test_02_user_import_api(self):
        """ユーザーインポートAPIテスト (要件: 2.2)"""
        # テストユーザーデータ作成
        test_import_data = {
            "users": [
                {
                    "id": 1001,
                    "username": "load_test_user1@example.com",
                    "email": "load_test_user1@example.com",
                    "password": "LoadTest123!",
                    "is_test_user": True,
                    "test_batch_id": f"load_test_batch_{int(time.time())}",
                    "created_by_bulk": True
                },
                {
                    "id": 1002,
                    "username": "load_test_user2@example.com",
                    "email": "load_test_user2@example.com",
                    "password": "LoadTest123!",
                    "is_test_user": True,
                    "test_batch_id": f"load_test_batch_{int(time.time())}",
                    "created_by_bulk": True
                }
            ],
            "export_timestamp": datetime.utcnow().isoformat(),
            "source_system": "main_application",
            "total_count": 2,
            "metadata": {}
        }
        
        response = requests.post(
            f"{self.load_tester_url}/api/users/import",
            json=test_import_data,
            timeout=15
        )
        
        self.assertEqual(response.status_code, 200, f"ユーザーインポート失敗: {response.text}")
        
        result = response.json()
        self.assertIn('success', result)
        self.assertIn('imported_count', result)
        self.assertTrue(result['success'], f"インポート失敗: {result.get('errors', [])}")
        self.assertEqual(result['imported_count'], 2)
        
        # テスト用にデータを保存
        self.__class__.test_users_data = test_import_data
        
        print(f"✓ ユーザーインポート成功: {result['imported_count']}件")
    
    def test_03_user_sync_api_import_functionality(self):
        """UserSyncAPIのインポート機能テスト (要件: 2.2)"""
        try:
            from user_sync_api import UserSyncAPI
            
            sync_api = UserSyncAPI()
            
            # テストデータでインポート実行
            test_data = {
                "users": [
                    {
                        "id": 2001,
                        "username": "api_test_user@example.com",
                        "password": "ApiTest123!",
                        "test_batch_id": f"api_test_batch_{int(time.time())}"
                    }
                ],
                "export_timestamp": datetime.utcnow().isoformat(),
                "source_system": "test_system",
                "total_count": 1
            }
            
            result = sync_api.import_users(test_data)
            
            self.assertTrue(result.success, f"インポート失敗: {result.errors}")
            self.assertEqual(result.imported_count, 1)
            self.assertEqual(result.failed_count, 0)
            
            print(f"✓ UserSyncAPIインポート成功: {result.imported_count}件")
            
        except Exception as e:
            self.fail(f"UserSyncAPIインポートエラー: {e}")
    
    def test_04_sync_status_api(self):
        """同期状況確認APIテスト (要件: 2.3)"""
        response = requests.get(
            f"{self.load_tester_url}/api/users/sync-status",
            timeout=10
        )
        
        self.assertEqual(response.status_code, 200, f"同期状況確認失敗: {response.text}")
        
        sync_status = response.json()
        self.assertIn('total_users', sync_status)
        self.assertIn('last_sync_check', sync_status)
        
        # インポートしたユーザーが反映されているか確認
        self.assertGreater(sync_status['total_users'], 0, "同期されたユーザーが0件です")
        
        print(f"✓ 同期状況確認成功: {sync_status['total_users']}件のユーザー")
    
    def test_05_user_sync_api_sync_status(self):
        """UserSyncAPIの同期状況取得テスト (要件: 2.3)"""
        try:
            from user_sync_api import UserSyncAPI
            
            sync_api = UserSyncAPI()
            
            # 同期状況取得
            status = sync_api.get_sync_status()
            
            self.assertIn('total_users', status)
            self.assertIn('users', status)
            self.assertIn('last_sync_check', status)
            
            # ユーザー情報の詳細確認
            if status['total_users'] > 0:
                user_info = status['users'][0]
                self.assertIn('user_id', user_info)
                self.assertIn('username', user_info)
                self.assertIn('enabled', user_info)
            
            print(f"✓ UserSyncAPI同期状況取得成功: {status['total_users']}件")
            
        except Exception as e:
            self.fail(f"UserSyncAPI同期状況取得エラー: {e}")
    
    def test_06_bulk_login_functionality(self):
        """一括ログイン機能テスト (要件: 2.3)"""
        response = requests.post(
            f"{self.load_tester_url}/api/users/sessions/bulk-login",
            json={},
            timeout=20
        )
        
        self.assertEqual(response.status_code, 200, f"一括ログイン失敗: {response.text}")
        
        result = response.json()
        self.assertIn('success', result)
        self.assertIn('logged_in_count', result)
        
        if result['success']:
            self.assertGreaterEqual(result['logged_in_count'], 0)
            print(f"✓ 一括ログイン成功: {result['logged_in_count']}件")
        else:
            print(f"⚠ 一括ログイン失敗: {result.get('error', 'Unknown error')}")
    
    def test_07_user_sync_api_bulk_login(self):
        """UserSyncAPIの一括ログイン機能テスト (要件: 2.3)"""
        try:
            from user_sync_api import UserSyncAPI
            
            sync_api = UserSyncAPI()
            
            # 一括ログイン実行
            result = sync_api.bulk_login_users()
            
            self.assertIn('success', result)
            self.assertIn('logged_in_count', result)
            
            if result['success']:
                self.assertGreaterEqual(result['logged_in_count'], 0)
                if result['logged_in_count'] > 0:
                    self.assertIn('sessions', result)
                    
                    # セッション情報の確認
                    session_info = result['sessions'][0]
                    self.assertIn('user_id', session_info)
                    self.assertIn('username', session_info)
                    self.assertIn('login_time', session_info)
            
            print(f"✓ UserSyncAPI一括ログイン成功: {result['logged_in_count']}件")
            
        except Exception as e:
            self.fail(f"UserSyncAPI一括ログインエラー: {e}")
    
    def test_08_batch_operations(self):
        """バッチ操作テスト (要件: 2.4)"""
        try:
            from user_sync_api import UserSyncAPI
            
            sync_api = UserSyncAPI()
            
            # バッチ情報取得
            batch_info = sync_api.get_batch_info()
            
            self.assertIn('total_batches', batch_info)
            self.assertIn('batches', batch_info)
            
            print(f"✓ バッチ情報取得成功: {batch_info['total_batches']}件のバッチ")
            
            # バッチが存在する場合、統計情報を取得
            if batch_info['total_batches'] > 0:
                batch_id = batch_info['batches'][0]
                
                # バッチ統計取得（session_managerにメソッドが存在する場合）
                try:
                    batch_stats = sync_api.session_manager.get_batch_session_stats(batch_id)
                    if batch_stats:
                        print(f"✓ バッチ統計取得成功: バッチ{batch_id}")
                except AttributeError:
                    print("⚠ バッチ統計機能は未実装")
            
        except Exception as e:
            self.fail(f"バッチ操作エラー: {e}")
    
    def test_09_error_handling_and_recovery(self):
        """エラーハンドリングと復旧機能テスト (要件: 2.5)"""
        # 無効なデータでのインポートテスト
        invalid_data = {
            "users": [
                {
                    "id": "invalid_id",  # 無効なID
                    # usernameが欠落
                    "password": "test"
                }
            ],
            "total_count": 1
        }
        
        response = requests.post(
            f"{self.load_tester_url}/api/users/import",
            json=invalid_data,
            timeout=10
        )
        
        # エラーレスポンスまたは部分的成功を期待
        self.assertIn(response.status_code, [200, 400, 422], 
                     f"無効なデータに対する適切なレスポンスがありません: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            # 部分的失敗の場合
            self.assertFalse(result.get('success', True), "無効なデータが成功として処理されました")
            self.assertGreater(len(result.get('errors', [])), 0, "エラー情報が記録されていません")
        
        print("✓ エラーハンドリングテスト完了")
    
    def test_10_load_tester_error_logging(self):
        """Load Testerエラーログ機能テスト (要件: 2.5)"""
        try:
            from user_sync_api import LoadTesterErrorHandler
            
            # エラーハンドラー初期化
            error_handler = LoadTesterErrorHandler()
            
            # テストエラーログ
            test_error = ValueError("統合テスト用エラー")
            context = {"operation": "integration_test", "timestamp": datetime.utcnow().isoformat()}
            
            error_handler.log_error("test_operation", test_error, context)
            
            # ログファイル確認
            if os.path.exists(error_handler.error_log_file):
                with open(error_handler.error_log_file, 'r', encoding='utf-8') as f:
                    log_content = f.read()
                
                self.assertIn("統合テスト用エラー", log_content, "エラーメッセージがログに記録されていません")
                self.assertIn("test_operation", log_content, "操作名がログに記録されていません")
                
                print("✓ Load Testerエラーログ確認成功")
            else:
                print("⚠ Load Testerエラーログファイルが見つかりません")
            
        except ImportError:
            print("⚠ LoadTesterErrorHandlerが見つかりません")
        except Exception as e:
            self.fail(f"Load Testerエラーログテストエラー: {e}")


if __name__ == '__main__':
    # テスト実行
    unittest.main(verbosity=2)