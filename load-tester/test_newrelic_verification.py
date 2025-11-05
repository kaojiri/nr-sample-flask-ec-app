#!/usr/bin/env python3
"""
New Relic検証機能のテストスクリプト
"""
import asyncio
import sys
import os
import logging
from datetime import datetime

# パスを追加してモジュールをインポート
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from newrelic_verification import verification_service
from automated_test_scenarios import test_runner, PREDEFINED_TEST_SUITES

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_newrelic_api_connection():
    """New Relic API接続テスト"""
    print("=" * 60)
    print("New Relic API接続テスト")
    print("=" * 60)
    
    if not verification_service.is_enabled():
        print("❌ New Relic検証機能が無効です")
        print("   - API キーまたはアカウントIDが設定されていません")
        print("   - 環境変数 NEW_RELIC_API_KEY と NEW_RELIC_ACCOUNT_ID を設定してください")
        return False
    
    print("✅ New Relic検証機能が有効です")
    print(f"   - 監視対象アプリ: {', '.join(verification_service.app_names)}")
    
    # 簡単なAPI接続テスト
    try:
        # ダミーのユーザーIDでCustom Attribute検証をテスト
        test_user_ids = ["test_user_1"]
        result = verification_service.verify_custom_attributes(
            expected_user_ids=test_user_ids,
            wait_time_seconds=5  # 短時間でテスト
        )
        
        if result.get("status") == "success":
            print("✅ New Relic API接続テスト成功")
            return True
        elif result.get("status") == "disabled":
            print("❌ New Relic検証機能が無効です")
            return False
        else:
            print(f"⚠️  New Relic API接続テスト部分成功: {result.get('status')}")
            if "error" in result:
                print(f"   エラー: {result['error']}")
            return True  # 接続自体は成功している
            
    except Exception as e:
        print(f"❌ New Relic API接続テストでエラー: {e}")
        return False

def test_distributed_service_connection():
    """分散サービス接続テスト"""
    print("\n" + "=" * 60)
    print("分散サービス接続テスト")
    print("=" * 60)
    
    from distributed_service_client import SyncDistributedServiceTestClient
    
    client = SyncDistributedServiceTestClient()
    
    # 直接呼び出しテスト
    print("分散サービスへの直接呼び出しテスト...")
    try:
        result = client.test_direct_call("n-plus-one", 1, timeout=10)
        if result.get("status") == "success":
            print("✅ 分散サービス直接呼び出し成功")
            print(f"   レスポンス時間: {result.get('response_time', 0):.2f}ms")
        else:
            print(f"❌ 分散サービス直接呼び出し失敗: {result.get('error', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"❌ 分散サービス直接呼び出しでエラー: {e}")
        return False
    
    # メインアプリ経由呼び出しテスト
    print("\nメインアプリ経由での呼び出しテスト...")
    try:
        result = client.test_via_main_app("n-plus-one", 1, timeout=10)
        if result.get("status") == "success":
            print("✅ メインアプリ経由呼び出し成功")
            print(f"   レスポンス時間: {result.get('response_time', 0):.2f}ms")
        else:
            print(f"❌ メインアプリ経由呼び出し失敗: {result.get('error', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"❌ メインアプリ経由呼び出しでエラー: {e}")
        return False
    
    return True

async def test_basic_automated_scenario():
    """基本的な自動化シナリオのテスト"""
    print("\n" + "=" * 60)
    print("基本自動化シナリオテスト")
    print("=" * 60)
    
    try:
        # 基本検証テストスイートを実行
        suite_config = PREDEFINED_TEST_SUITES["basic_verification"]
        # テストユーザー数を少なくして高速化
        suite_config.test_users_count = 2
        suite_config.verification_enabled = verification_service.is_enabled()
        
        print(f"テストスイート '{suite_config.name}' を実行中...")
        print(f"New Relic検証: {'有効' if suite_config.verification_enabled else '無効'}")
        
        result = await test_runner.run_test_suite(suite_config)
        
        if result["overall_status"] in ["success", "partial"]:
            print("✅ 基本自動化シナリオテスト成功")
            print(f"   全体ステータス: {result['overall_status']}")
            print(f"   成功シナリオ: {result['summary']['successful_scenarios']}/{result['summary']['total_scenarios']}")
            print(f"   成功リクエスト: {result['summary']['successful_requests']}/{result['summary']['total_requests']}")
            return True
        else:
            print(f"❌ 基本自動化シナリオテスト失敗: {result['overall_status']}")
            if "error" in result:
                print(f"   エラー: {result['error']}")
            return False
            
    except Exception as e:
        print(f"❌ 基本自動化シナリオテストでエラー: {e}")
        return False

async def main():
    """メイン関数"""
    print("New Relic検証機能テストスイート")
    print(f"実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    test_results = []
    
    # 1. New Relic API接続テスト
    newrelic_ok = test_newrelic_api_connection()
    test_results.append(("New Relic API接続", newrelic_ok))
    
    # 2. 分散サービス接続テスト
    distributed_ok = test_distributed_service_connection()
    test_results.append(("分散サービス接続", distributed_ok))
    
    # 3. 基本自動化シナリオテスト（前の2つが成功した場合のみ）
    if newrelic_ok and distributed_ok:
        scenario_ok = await test_basic_automated_scenario()
        test_results.append(("基本自動化シナリオ", scenario_ok))
    else:
        print("\n⚠️  前提条件が満たされていないため、自動化シナリオテストをスキップします")
        test_results.append(("基本自動化シナリオ", False))
    
    # 結果サマリー
    print("\n" + "=" * 60)
    print("テスト結果サマリー")
    print("=" * 60)
    
    passed_tests = 0
    for test_name, result in test_results:
        status = "✅ 成功" if result else "❌ 失敗"
        print(f"{test_name}: {status}")
        if result:
            passed_tests += 1
    
    print(f"\n総合結果: {passed_tests}/{len(test_results)} テスト成功")
    
    if passed_tests == len(test_results):
        print("🎉 すべてのテストが成功しました！")
        return 0
    elif passed_tests > 0:
        print("⚠️  一部のテストが失敗しました")
        return 1
    else:
        print("❌ すべてのテストが失敗しました")
        return 2

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nテストが中断されました")
        sys.exit(1)
    except Exception as e:
        print(f"予期しないエラー: {e}")
        sys.exit(1)