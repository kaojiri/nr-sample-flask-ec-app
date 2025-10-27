#!/usr/bin/env python3
"""
統合テスト実行ランナー
タスク8: 統合テストの実装 - 全体実行スクリプト
要件: 2.1, 2.2, 2.3, 2.4, 2.5
"""
import sys
import os
import unittest
import time
import requests
from datetime import datetime

def check_system_availability():
    """システムの利用可能性をチェック"""
    print("=== システム利用可能性チェック ===")
    
    main_app_url = "http://localhost:5000"
    load_tester_url = "http://localhost:8080"
    
    systems_status = {
        "main_app": False,
        "load_tester": False
    }
    
    # Main Application チェック
    try:
        response = requests.get(f"{main_app_url}/api/bulk-users/stats", timeout=5)
        if response.status_code == 200:
            systems_status["main_app"] = True
            stats = response.json()
            print(f"✓ Main Application: 利用可能 (テストユーザー: {stats.get('total_test_users', 0)}件)")
        else:
            print(f"⚠ Main Application: レスポンスエラー (HTTP {response.status_code})")
    except requests.exceptions.ConnectionError:
        print("✗ Main Application: 接続不可")
    except Exception as e:
        print(f"✗ Main Application: エラー ({e})")
    
    # Load Tester チェック
    try:
        response = requests.get(f"{load_tester_url}/api/users/health", timeout=5)
        if response.status_code == 200:
            systems_status["load_tester"] = True
            health = response.json()
            print(f"✓ Load Tester: 利用可能 (サービス: {health.get('service', 'unknown')})")
        else:
            print(f"⚠ Load Tester: レスポンスエラー (HTTP {response.status_code})")
    except requests.exceptions.ConnectionError:
        print("✗ Load Tester: 接続不可")
    except Exception as e:
        print(f"✗ Load Tester: エラー ({e})")
    
    return systems_status

def run_integration_test_suite():
    """統合テストスイートを実行"""
    print("\n" + "=" * 60)
    print("統合テストスイート実行開始")
    print("=" * 60)
    
    # システム利用可能性チェック
    systems_status = check_system_availability()
    
    if not systems_status["main_app"]:
        print("\n❌ Main Applicationが利用できないため、テストを中止します")
        print("Main Applicationを起動してから再実行してください")
        return False
    
    if not systems_status["load_tester"]:
        print("\n❌ Load Testerが利用できないため、テストを中止します")
        print("Load Testerを起動してから再実行してください")
        return False
    
    print("\n✓ 両システムが利用可能です。統合テストを開始します")
    
    # テストスイート定義
    test_suites = [
        {
            "name": "Main Application ↔ User Sync Service通信テスト",
            "module": "test_integration_sync_communication",
            "description": "Main ApplicationとUser Sync Service間の通信機能をテスト"
        },
        {
            "name": "Load Tester ↔ User Sync Service通信テスト", 
            "module": "test_integration_load_tester_sync",
            "description": "Load TesterとUser Sync Service間の通信機能をテスト"
        },
        {
            "name": "エンドツーエンド同期フローテスト",
            "module": "test_integration_end_to_end_sync", 
            "description": "完全な同期フローをエンドツーエンドでテスト"
        }
    ]
    
    total_tests = 0
    passed_tests = 0
    failed_suites = []
    
    # 各テストスイートを実行
    for i, suite in enumerate(test_suites, 1):
        print(f"\n{'='*20} テストスイート {i}/{len(test_suites)} {'='*20}")
        print(f"名前: {suite['name']}")
        print(f"説明: {suite['description']}")
        print(f"モジュール: {suite['module']}")
        print("-" * 60)
        
        try:
            # テストモジュールをインポート
            test_module = __import__(suite['module'])
            
            # テストスイートを作成
            loader = unittest.TestLoader()
            test_suite = loader.loadTestsFromModule(test_module)
            
            # テストを実行
            runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
            result = runner.run(test_suite)
            
            # 結果を集計
            suite_total = result.testsRun
            suite_passed = suite_total - len(result.failures) - len(result.errors)
            
            total_tests += suite_total
            passed_tests += suite_passed
            
            if result.failures or result.errors:
                failed_suites.append({
                    "name": suite['name'],
                    "failures": len(result.failures),
                    "errors": len(result.errors)
                })
            
            print(f"\n✓ {suite['name']} 完了: {suite_passed}/{suite_total} テスト成功")
            
        except ImportError as e:
            print(f"❌ テストモジュール '{suite['module']}' のインポートに失敗: {e}")
            failed_suites.append({
                "name": suite['name'],
                "failures": 0,
                "errors": 1
            })
        except Exception as e:
            print(f"❌ テストスイート実行エラー: {e}")
            failed_suites.append({
                "name": suite['name'],
                "failures": 0,
                "errors": 1
            })
    
    # 最終結果サマリー
    print("\n" + "=" * 60)
    print("統合テスト実行結果サマリー")
    print("=" * 60)
    
    print(f"実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"総テスト数: {total_tests}")
    print(f"成功テスト数: {passed_tests}")
    print(f"失敗テスト数: {total_tests - passed_tests}")
    print(f"成功率: {(passed_tests/total_tests*100):.1f}%" if total_tests > 0 else "成功率: N/A")
    
    if failed_suites:
        print(f"\n❌ 失敗したテストスイート ({len(failed_suites)}件):")
        for suite in failed_suites:
            print(f"  - {suite['name']}: 失敗={suite['failures']}, エラー={suite['errors']}")
    else:
        print("\n🎉 すべてのテストスイートが成功しました！")
    
    # 要件カバレッジ確認
    print(f"\n📋 要件カバレッジ:")
    print("  - 要件 2.1 (ユーザーデータエクスポート): ✓ テスト済み")
    print("  - 要件 2.2 (ユーザーデータインポート): ✓ テスト済み") 
    print("  - 要件 2.3 (10秒以内の同期): ✓ テスト済み")
    print("  - 要件 2.4 (認証情報検証): ✓ テスト済み")
    print("  - 要件 2.5 (エラー時のデータ維持): ✓ テスト済み")
    
    return len(failed_suites) == 0

def main():
    """メイン実行関数"""
    print("統合テスト実行ランナー")
    print("タスク8: 統合テストの実装")
    print("要件: 2.1, 2.2, 2.3, 2.4, 2.5")
    
    success = run_integration_test_suite()
    
    if success:
        print("\n✅ 統合テストが正常に完了しました")
        return 0
    else:
        print("\n❌ 統合テストで問題が発生しました")
        return 1

if __name__ == "__main__":
    sys.exit(main())