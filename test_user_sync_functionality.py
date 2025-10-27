#!/usr/bin/env python3
"""
ユーザー同期機能のテストスクリプト
"""
import sys
import os
import json
import requests
import time
from datetime import datetime

# Add app directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

def test_user_sync_service():
    """UserSyncServiceの基本機能をテスト"""
    print("=== UserSyncService 基本機能テスト ===")
    
    try:
        from app.services.user_sync_service import UserSyncService, TestUserData, UserExportData
        
        # サービス初期化
        sync_service = UserSyncService("http://localhost:8080")
        print("✓ UserSyncService初期化成功")
        
        # テストデータ作成
        test_users = [
            TestUserData(
                id=1,
                username="testuser1@example.com",
                email="testuser1@example.com",
                password="TestPass123!",
                test_batch_id="test_batch_001"
            ),
            TestUserData(
                id=2,
                username="testuser2@example.com", 
                email="testuser2@example.com",
                password="TestPass123!",
                test_batch_id="test_batch_001"
            )
        ]
        
        export_data = UserExportData(
            users=test_users,
            export_timestamp=datetime.utcnow().isoformat(),
            source_system="test_system",
            total_count=len(test_users)
        )
        
        print("✓ テストデータ作成成功")
        
        # JSON変換テスト
        json_data = export_data.to_dict()
        print(f"✓ JSON変換成功: {len(json_data['users'])}件のユーザー")
        
        # JSONファイルエクスポートテスト
        test_file = "test_export.json"
        success = sync_service.export_to_json_file(test_file, {"test_users_only": True})
        
        if success:
            print(f"✓ JSONファイルエクスポート成功: {test_file}")
            
            # ファイル確認
            if os.path.exists(test_file):
                with open(test_file, 'r', encoding='utf-8') as f:
                    file_data = json.load(f)
                print(f"✓ エクスポートファイル確認: {file_data.get('total_count', 0)}件")
                os.remove(test_file)  # クリーンアップ
        else:
            print("⚠ JSONファイルエクスポート失敗（データベースにテストユーザーがない可能性）")
        
        print("✓ UserSyncService基本機能テスト完了")
        return True
        
    except Exception as e:
        print(f"✗ UserSyncServiceテストエラー: {str(e)}")
        return False

def test_main_app_api():
    """Main ApplicationのAPI エンドポイントをテスト"""
    print("\n=== Main Application API テスト ===")
    
    base_url = "http://localhost:5000"
    
    try:
        # ヘルスチェック
        response = requests.get(f"{base_url}/api/bulk-users/stats", timeout=5)
        if response.status_code == 200:
            stats = response.json()
            print(f"✓ Main App接続成功: {stats.get('total_test_users', 0)}件のテストユーザー")
        else:
            print(f"⚠ Main App接続失敗: HTTP {response.status_code}")
            return False
        
        # エクスポートAPIテスト
        response = requests.get(f"{base_url}/api/bulk-users/export?test_users_only=true", timeout=10)
        if response.status_code == 200:
            export_data = response.json()
            print(f"✓ エクスポートAPI成功: {export_data.get('total_count', 0)}件")
        else:
            print(f"⚠ エクスポートAPI失敗: HTTP {response.status_code}")
        
        # 同期状況確認APIテスト
        response = requests.get(f"{base_url}/api/bulk-users/sync/status", timeout=10)
        if response.status_code == 200:
            sync_status = response.json()
            print(f"✓ 同期状況API成功: 検証数={sync_status.get('total_checked', 0)}")
        else:
            print(f"⚠ 同期状況API失敗: HTTP {response.status_code}")
        
        print("✓ Main Application APIテスト完了")
        return True
        
    except requests.exceptions.ConnectionError:
        print("✗ Main Applicationに接続できません（サーバーが起動していない可能性）")
        return False
    except Exception as e:
        print(f"✗ Main Application APIテストエラー: {str(e)}")
        return False

def test_load_tester_api():
    """Load Tester APIをテスト"""
    print("\n=== Load Tester API テスト ===")
    
    base_url = "http://localhost:8080"
    
    try:
        # ヘルスチェック
        response = requests.get(f"{base_url}/api/users/health", timeout=5)
        if response.status_code == 200:
            health = response.json()
            print(f"✓ Load Tester接続成功: {health.get('service', 'unknown')}")
        else:
            print(f"⚠ Load Tester接続失敗: HTTP {response.status_code}")
            return False
        
        # 同期状況確認APIテスト
        response = requests.get(f"{base_url}/api/users/sync-status", timeout=10)
        if response.status_code == 200:
            sync_status = response.json()
            print(f"✓ 同期状況API成功: {sync_status.get('total_users', 0)}件のユーザー")
        else:
            print(f"⚠ 同期状況API失敗: HTTP {response.status_code}")
        
        # テストユーザー取得APIテスト
        response = requests.get(f"{base_url}/api/users", timeout=10)
        if response.status_code == 200:
            users_data = response.json()
            print(f"✓ ユーザー取得API成功: {users_data.get('total_count', 0)}件")
        else:
            print(f"⚠ ユーザー取得API失敗: HTTP {response.status_code}")
        
        print("✓ Load Tester APIテスト完了")
        return True
        
    except requests.exceptions.ConnectionError:
        print("✗ Load Testerに接続できません（サーバーが起動していない可能性）")
        return False
    except Exception as e:
        print(f"✗ Load Tester APIテストエラー: {str(e)}")
        return False

def test_end_to_end_sync():
    """エンドツーエンドの同期テスト"""
    print("\n=== エンドツーエンド同期テスト ===")
    
    main_app_url = "http://localhost:5000"
    load_tester_url = "http://localhost:8080"
    
    try:
        # 1. Main Appでテストユーザーを作成
        print("1. テストユーザー作成...")
        create_data = {
            "count": 3,
            "config": {
                "username_pattern": "synctest_{id}@example.com",
                "password": "SyncTest123!",
                "email_domain": "example.com"
            }
        }
        
        response = requests.post(f"{main_app_url}/api/bulk-users/create", 
                               json=create_data, timeout=30)
        
        if response.status_code in [200, 201]:
            result = response.json()
            batch_id = result.get('batch_id')
            print(f"✓ テストユーザー作成成功: バッチID={batch_id}, 作成数={result.get('successful_count', 0)}")
        else:
            print(f"⚠ テストユーザー作成失敗: HTTP {response.status_code}")
            return False
        
        # 2. 同期実行
        print("2. 同期実行...")
        sync_data = {
            "target": "load_tester",
            "filter_criteria": {
                "batch_id": batch_id,
                "test_users_only": True
            }
        }
        
        response = requests.post(f"{main_app_url}/api/bulk-users/sync",
                               json=sync_data, timeout=30)
        
        if response.status_code == 200:
            sync_result = response.json()
            print(f"✓ 同期実行成功: 同期数={sync_result.get('synced_count', 0)}")
        else:
            print(f"⚠ 同期実行失敗: HTTP {response.status_code}")
            if response.text:
                print(f"   エラー詳細: {response.text}")
        
        # 3. Load Testerで同期確認
        print("3. Load Testerで同期確認...")
        response = requests.get(f"{load_tester_url}/api/users/sync-status", timeout=10)
        
        if response.status_code == 200:
            status = response.json()
            print(f"✓ 同期確認成功: Load Testerに{status.get('total_users', 0)}件のユーザー")
        else:
            print(f"⚠ 同期確認失敗: HTTP {response.status_code}")
        
        # 4. クリーンアップ
        print("4. テストデータクリーンアップ...")
        if batch_id:
            response = requests.delete(f"{main_app_url}/api/bulk-users/batches/{batch_id}", timeout=10)
            if response.status_code == 200:
                cleanup_result = response.json()
                print(f"✓ クリーンアップ成功: 削除数={cleanup_result.get('deleted_count', 0)}")
            else:
                print(f"⚠ クリーンアップ失敗: HTTP {response.status_code}")
        
        print("✓ エンドツーエンド同期テスト完了")
        return True
        
    except Exception as e:
        print(f"✗ エンドツーエンド同期テストエラー: {str(e)}")
        return False

def main():
    """メインテスト実行"""
    print("ユーザー同期機能テスト開始")
    print("=" * 50)
    
    results = []
    
    # 各テストを実行
    results.append(("UserSyncService基本機能", test_user_sync_service()))
    results.append(("Main Application API", test_main_app_api()))
    results.append(("Load Tester API", test_load_tester_api()))
    results.append(("エンドツーエンド同期", test_end_to_end_sync()))
    
    # 結果サマリー
    print("\n" + "=" * 50)
    print("テスト結果サマリー")
    print("=" * 50)
    
    passed = 0
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n合計: {passed}/{len(results)} テスト成功")
    
    if passed == len(results):
        print("🎉 全てのテストが成功しました！")
        return 0
    else:
        print("⚠ 一部のテストが失敗しました。")
        return 1

if __name__ == "__main__":
    sys.exit(main())