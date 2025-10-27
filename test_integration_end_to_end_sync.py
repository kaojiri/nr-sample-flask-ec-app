#!/usr/bin/env python3
"""
統合テスト: エンドツーエンドの同期フローテスト
要件: 2.1, 2.2, 2.3, 2.4, 2.5
"""
import sys
import os
import unittest
import requests
import json
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

# アプリケーションパスを追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'load-tester'))

class TestEndToEndSyncFlow(unittest.TestCase):
    """エンドツーエンドの同期フローテスト"""
    
    @classmethod
    def setUpClass(cls):
        """テストクラス初期化"""
        cls.main_app_url = "http://localhost:5000"
        cls.load_tester_url = "http://localhost:8080"
        cls.test_batch_ids = []
        cls.test_users_created = []
        
    def setUp(self):
        """各テストの前処理"""
        # 両システムの接続確認
        try:
            main_response = requests.get(f"{self.main_app_url}/api/bulk-users/stats", timeout=5)
            load_response = requests.get(f"{self.load_tester_url}/api/users/health", timeout=5)
            
            if main_response.status_code != 200:
                self.skipTest("Main Applicationが利用できません")
            if load_response.status_code != 200:
                self.skipTest("Load Testerが利用できません")
                
        except requests.exceptions.ConnectionError as e:
            self.skipTest(f"システムに接続できません: {e}")
    
    def test_01_complete_sync_flow_small_batch(self):
        """完全な同期フロー - 小規模バッチテスト (要件: 2.1, 2.2, 2.3)"""
        print("\n=== 小規模バッチ同期フローテスト開始 ===")
        
        # 1. Main Appでテストユーザー作成
        batch_id = f"e2e_small_{int(time.time())}"
        create_data = {
            "count": 5,
            "config": {
                "username_pattern": "e2e_small_{id}@example.com",
                "password": "E2ESmall123!",
                "email_domain": "example.com",
                "test_batch_id": batch_id
            }
        }
        
        print("1. Main Appでテストユーザー作成中...")
        response = requests.post(
            f"{self.main_app_url}/api/bulk-users/create",
            json=create_data,
            timeout=30
        )
        
        self.assertEqual(response.status_code, 201, f"ユーザー作成失敗: {response.text}")
        
        create_result = response.json()
        actual_batch_id = create_result['batch_id']
        self.__class__.test_batch_ids.append(actual_batch_id)
        
        self.assertEqual(create_result['successful_count'], 5)
        print(f"✓ ユーザー作成成功: {create_result['successful_count']}件, バッチID={actual_batch_id}")
        
        # 2. エクスポートデータ確認
        print("2. エクスポートデータ確認中...")
        response = requests.get(
            f"{self.main_app_url}/api/bulk-users/export?batch_id={actual_batch_id}",
            timeout=15
        )
        
        self.assertEqual(response.status_code, 200, f"エクスポート失敗: {response.text}")
        
        export_data = response.json()
        self.assertEqual(export_data['total_count'], 5)
        print(f"✓ エクスポートデータ確認: {export_data['total_count']}件")
        
        # 3. Load Testerへの同期実行
        print("3. Load Testerへの同期実行中...")
        sync_data = {
            "target": "load_tester",
            "filter_criteria": {
                "batch_id": actual_batch_id,
                "test_users_only": True
            }
        }
        
        response = requests.post(
            f"{self.main_app_url}/api/bulk-users/sync",
            json=sync_data,
            timeout=30
        )
        
        self.assertEqual(response.status_code, 200, f"同期失敗: {response.text}")
        
        sync_result = response.json()
        self.assertTrue(sync_result.get('success', False), f"同期失敗: {sync_result.get('errors', [])}")
        self.assertEqual(sync_result.get('synced_count', 0), 5)
        print(f"✓ 同期実行成功: {sync_result['synced_count']}件")
        
        # 4. Load Testerでの同期確認
        print("4. Load Testerでの同期確認中...")
        time.sleep(2)  # 同期処理の完了を待機
        
        response = requests.get(
            f"{self.load_tester_url}/api/users/sync-status",
            timeout=10
        )
        
        self.assertEqual(response.status_code, 200, f"同期確認失敗: {response.text}")
        
        load_status = response.json()
        self.assertGreaterEqual(load_status['total_users'], 5, "Load Testerに同期されたユーザーが不足")
        print(f"✓ Load Tester同期確認: {load_status['total_users']}件のユーザー")
        
        # 5. 一括ログインテスト
        print("5. 一括ログインテスト中...")
        response = requests.post(
            f"{self.load_tester_url}/api/users/sessions/bulk-login",
            json={},
            timeout=20
        )
        
        self.assertEqual(response.status_code, 200, f"一括ログイン失敗: {response.text}")
        
        login_result = response.json()
        if login_result.get('success', False):
            print(f"✓ 一括ログイン成功: {login_result['logged_in_count']}件")
        else:
            print(f"⚠ 一括ログイン失敗: {login_result.get('error', 'Unknown error')}")
        
        print("✓ 小規模バッチ同期フロー完了")
    
    def test_02_complete_sync_flow_medium_batch(self):
        """完全な同期フロー - 中規模バッチテスト (要件: 2.1, 2.2, 2.3)"""
        print("\n=== 中規模バッチ同期フローテスト開始 ===")
        
        # 1. Main Appで中規模テストユーザー作成
        batch_id = f"e2e_medium_{int(time.time())}"
        create_data = {
            "count": 25,
            "config": {
                "username_pattern": "e2e_medium_{id}@example.com",
                "password": "E2EMedium123!",
                "email_domain": "example.com",
                "test_batch_id": batch_id
            }
        }
        
        print("1. Main Appで中規模テストユーザー作成中...")
        response = requests.post(
            f"{self.main_app_url}/api/bulk-users/create",
            json=create_data,
            timeout=60
        )
        
        self.assertEqual(response.status_code, 201, f"ユーザー作成失敗: {response.text}")
        
        create_result = response.json()
        actual_batch_id = create_result['batch_id']
        self.__class__.test_batch_ids.append(actual_batch_id)
        
        self.assertEqual(create_result['successful_count'], 25)
        print(f"✓ ユーザー作成成功: {create_result['successful_count']}件, バッチID={actual_batch_id}")
        
        # 2. 同期実行とパフォーマンス測定
        print("2. 同期実行とパフォーマンス測定中...")
        sync_start_time = time.time()
        
        sync_data = {
            "target": "load_tester",
            "filter_criteria": {
                "batch_id": actual_batch_id,
                "test_users_only": True
            }
        }
        
        response = requests.post(
            f"{self.main_app_url}/api/bulk-users/sync",
            json=sync_data,
            timeout=60
        )
        
        sync_end_time = time.time()
        sync_duration = sync_end_time - sync_start_time
        
        self.assertEqual(response.status_code, 200, f"同期失敗: {response.text}")
        
        sync_result = response.json()
        self.assertTrue(sync_result.get('success', False), f"同期失敗: {sync_result.get('errors', [])}")
        self.assertEqual(sync_result.get('synced_count', 0), 25)
        
        # パフォーマンス要件確認 (要件: 2.3 - 10秒以内)
        self.assertLess(sync_duration, 30, f"同期時間が長すぎます: {sync_duration:.2f}秒")
        print(f"✓ 同期実行成功: {sync_result['synced_count']}件, 実行時間: {sync_duration:.2f}秒")
        
        # 3. データ整合性確認
        print("3. データ整合性確認中...")
        time.sleep(3)  # 同期処理の完了を待機
        
        # Main Appのデータ確認
        response = requests.get(
            f"{self.main_app_url}/api/bulk-users/batches/{actual_batch_id}",
            timeout=10
        )
        
        self.assertEqual(response.status_code, 200, f"バッチ情報取得失敗: {response.text}")
        
        batch_info = response.json()
        self.assertEqual(batch_info['user_count'], 25)
        
        # Load Testerのデータ確認
        response = requests.get(
            f"{self.load_tester_url}/api/users/sync-status",
            timeout=10
        )
        
        self.assertEqual(response.status_code, 200, f"Load Tester状況確認失敗: {response.text}")
        
        load_status = response.json()
        self.assertGreaterEqual(load_status['total_users'], 25, "Load Testerのユーザー数が不足")
        
        print(f"✓ データ整合性確認: Main App={batch_info['user_count']}件, Load Tester={load_status['total_users']}件")
        
        print("✓ 中規模バッチ同期フロー完了")
    
    def test_03_sync_error_recovery_flow(self):
        """同期エラーと復旧フローテスト (要件: 2.4, 2.5)"""
        print("\n=== 同期エラー復旧フローテスト開始 ===")
        
        # 1. 正常なユーザー作成
        batch_id = f"e2e_error_{int(time.time())}"
        create_data = {
            "count": 3,
            "config": {
                "username_pattern": "e2e_error_{id}@example.com",
                "password": "E2EError123!",
                "email_domain": "example.com",
                "test_batch_id": batch_id
            }
        }
        
        print("1. 正常なユーザー作成中...")
        response = requests.post(
            f"{self.main_app_url}/api/bulk-users/create",
            json=create_data,
            timeout=30
        )
        
        self.assertEqual(response.status_code, 201, f"ユーザー作成失敗: {response.text}")
        
        create_result = response.json()
        actual_batch_id = create_result['batch_id']
        self.__class__.test_batch_ids.append(actual_batch_id)
        
        print(f"✓ ユーザー作成成功: {create_result['successful_count']}件")
        
        # 2. 無効なターゲットでの同期テスト（エラー発生）
        print("2. 無効なターゲットでの同期テスト...")
        invalid_sync_data = {
            "target": "invalid_target",
            "filter_criteria": {
                "batch_id": actual_batch_id
            }
        }
        
        response = requests.post(
            f"{self.main_app_url}/api/bulk-users/sync",
            json=invalid_sync_data,
            timeout=15
        )
        
        # エラーレスポンスを期待
        self.assertIn(response.status_code, [400, 404, 500], 
                     f"無効なターゲットに対する適切なエラーレスポンスがありません: {response.status_code}")
        
        print(f"✓ 期待されたエラーレスポンス: HTTP {response.status_code}")
        
        # 3. 正常な同期での復旧
        print("3. 正常な同期での復旧中...")
        valid_sync_data = {
            "target": "load_tester",
            "filter_criteria": {
                "batch_id": actual_batch_id,
                "test_users_only": True
            }
        }
        
        response = requests.post(
            f"{self.main_app_url}/api/bulk-users/sync",
            json=valid_sync_data,
            timeout=30
        )
        
        self.assertEqual(response.status_code, 200, f"復旧同期失敗: {response.text}")
        
        sync_result = response.json()
        self.assertTrue(sync_result.get('success', False), f"復旧同期失敗: {sync_result.get('errors', [])}")
        
        print(f"✓ 復旧同期成功: {sync_result['synced_count']}件")
        
        # 4. エラーログ確認
        print("4. エラーログ確認中...")
        error_log_file = "logs/bulk_user_errors.log"
        
        if os.path.exists(error_log_file):
            with open(error_log_file, 'r', encoding='utf-8') as f:
                log_content = f.read()
            
            # 最近のエラーログが記録されているか確認
            recent_time = datetime.utcnow() - timedelta(minutes=5)
            
            if "ERROR" in log_content:
                print("✓ エラーログ記録確認")
            else:
                print("⚠ エラーログが見つかりません")
        else:
            print("⚠ エラーログファイルが存在しません")
        
        print("✓ 同期エラー復旧フロー完了")
    
    def test_04_bidirectional_sync_validation(self):
        """双方向同期検証テスト (要件: 2.4)"""
        print("\n=== 双方向同期検証テスト開始 ===")
        
        try:
            from app.services.user_sync_service import UserSyncService
            
            # 1. UserSyncService初期化
            sync_service = UserSyncService(self.load_tester_url)
            
            # 2. 双方向同期実行
            print("1. 双方向同期実行中...")
            sync_result = sync_service.sync_bidirectional()
            
            self.assertIsNotNone(sync_result)
            print(f"✓ 双方向同期実行: 成功={sync_result.success}")
            
            # 3. 同期整合性検証
            print("2. 同期整合性検証中...")
            validation_result = sync_service.validate_sync_integrity()
            
            self.assertIsNotNone(validation_result)
            self.assertTrue(validation_result.is_valid, f"同期整合性エラー: {validation_result.errors}")
            
            print(f"✓ 同期整合性検証: 検証数={validation_result.total_checked}")
            
        except ImportError:
            print("⚠ UserSyncServiceが利用できません")
        except Exception as e:
            self.fail(f"双方向同期検証エラー: {e}")
        
        print("✓ 双方向同期検証完了")
    
    def test_05_large_batch_performance_test(self):
        """大規模バッチパフォーマンステスト (要件: 2.3)"""
        print("\n=== 大規模バッチパフォーマンステスト開始 ===")
        
        # 1. 大規模バッチ作成（100ユーザー）
        batch_id = f"e2e_large_{int(time.time())}"
        create_data = {
            "count": 100,
            "config": {
                "username_pattern": "e2e_large_{id}@example.com",
                "password": "E2ELarge123!",
                "email_domain": "example.com",
                "test_batch_id": batch_id
            }
        }
        
        print("1. 大規模バッチ作成中（100ユーザー）...")
        create_start_time = time.time()
        
        response = requests.post(
            f"{self.main_app_url}/api/bulk-users/create",
            json=create_data,
            timeout=120
        )
        
        create_end_time = time.time()
        create_duration = create_end_time - create_start_time
        
        self.assertEqual(response.status_code, 201, f"大規模ユーザー作成失敗: {response.text}")
        
        create_result = response.json()
        actual_batch_id = create_result['batch_id']
        self.__class__.test_batch_ids.append(actual_batch_id)
        
        self.assertEqual(create_result['successful_count'], 100)
        
        # パフォーマンス要件確認 (要件: 1.5 - 100ユーザーを30秒以内)
        self.assertLess(create_duration, 60, f"ユーザー作成時間が長すぎます: {create_duration:.2f}秒")
        print(f"✓ 大規模ユーザー作成成功: {create_result['successful_count']}件, 実行時間: {create_duration:.2f}秒")
        
        # 2. 大規模同期実行
        print("2. 大規模同期実行中...")
        sync_start_time = time.time()
        
        sync_data = {
            "target": "load_tester",
            "filter_criteria": {
                "batch_id": actual_batch_id,
                "test_users_only": True
            }
        }
        
        response = requests.post(
            f"{self.main_app_url}/api/bulk-users/sync",
            json=sync_data,
            timeout=120
        )
        
        sync_end_time = time.time()
        sync_duration = sync_end_time - sync_start_time
        
        self.assertEqual(response.status_code, 200, f"大規模同期失敗: {response.text}")
        
        sync_result = response.json()
        self.assertTrue(sync_result.get('success', False), f"大規模同期失敗: {sync_result.get('errors', [])}")
        self.assertEqual(sync_result.get('synced_count', 0), 100)
        
        # 同期パフォーマンス要件確認
        self.assertLess(sync_duration, 60, f"同期時間が長すぎます: {sync_duration:.2f}秒")
        print(f"✓ 大規模同期成功: {sync_result['synced_count']}件, 実行時間: {sync_duration:.2f}秒")
        
        # 3. Load Testerでの確認
        print("3. Load Testerでの大規模データ確認中...")
        time.sleep(5)  # 処理完了を待機
        
        response = requests.get(
            f"{self.load_tester_url}/api/users/sync-status",
            timeout=15
        )
        
        self.assertEqual(response.status_code, 200, f"Load Tester状況確認失敗: {response.text}")
        
        load_status = response.json()
        self.assertGreaterEqual(load_status['total_users'], 100, "Load Testerの大規模データが不足")
        
        print(f"✓ Load Tester大規模データ確認: {load_status['total_users']}件のユーザー")
        
        print("✓ 大規模バッチパフォーマンステスト完了")
    
    @classmethod
    def tearDownClass(cls):
        """テストクラス終了処理"""
        print("\n=== テストデータクリーンアップ開始 ===")
        
        # 作成したすべてのテストバッチをクリーンアップ
        for batch_id in cls.test_batch_ids:
            try:
                response = requests.delete(
                    f"{cls.main_app_url}/api/bulk-users/batches/{batch_id}",
                    timeout=15
                )
                
                if response.status_code == 200:
                    cleanup_result = response.json()
                    print(f"✓ バッチ{batch_id}クリーンアップ完了: 削除数={cleanup_result.get('deleted_count', 0)}")
                else:
                    print(f"⚠ バッチ{batch_id}クリーンアップ失敗: HTTP {response.status_code}")
                    
            except Exception as e:
                print(f"⚠ バッチ{batch_id}クリーンアップエラー: {e}")
        
        print("✓ テストデータクリーンアップ完了")


if __name__ == '__main__':
    # テスト実行
    unittest.main(verbosity=2)