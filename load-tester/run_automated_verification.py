#!/usr/bin/env python3
"""
自動化された分散トレーシング検証テストの実行スクリプト
"""
import asyncio
import argparse
import sys
import logging
from datetime import datetime
from typing import Optional

from automated_test_scenarios import (
    test_runner, 
    PREDEFINED_TEST_SUITES,
    AutomatedTestSuite
)
from newrelic_verification import verification_service

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def print_banner():
    """バナーを表示"""
    print("=" * 80)
    print("  分散トレーシング自動検証テストスイート")
    print("  Distributed Tracing Automated Verification Test Suite")
    print("=" * 80)
    print()

def print_available_suites():
    """利用可能なテストスイートを表示"""
    print("利用可能なテストスイート:")
    print("-" * 40)
    for suite_name, suite_config in PREDEFINED_TEST_SUITES.items():
        print(f"  {suite_name}:")
        print(f"    名前: {suite_config.name}")
        print(f"    シナリオ: {', '.join(suite_config.scenarios)}")
        print(f"    テストユーザー数: {suite_config.test_users_count}")
        print(f"    New Relic検証: {'有効' if suite_config.verification_enabled else '無効'}")
        print()

def print_system_status():
    """システム状態を表示"""
    print("システム状態:")
    print("-" * 20)
    
    # New Relic検証機能の状態
    if verification_service.is_enabled():
        print("✓ New Relic検証機能: 有効")
        print(f"  - 監視対象アプリ: {', '.join(verification_service.app_names)}")
    else:
        print("✗ New Relic検証機能: 無効")
        print("  - API キーまたはアカウントIDが設定されていません")
    
    print()

async def run_test_suite(suite_name: str, 
                        custom_users: Optional[int] = None,
                        save_results: bool = True) -> bool:
    """指定されたテストスイートを実行"""
    
    if suite_name not in PREDEFINED_TEST_SUITES:
        logger.error(f"Unknown test suite: {suite_name}")
        return False
    
    suite_config = PREDEFINED_TEST_SUITES[suite_name]
    
    # カスタムユーザー数の適用
    if custom_users is not None:
        suite_config.test_users_count = custom_users
        logger.info(f"Using custom user count: {custom_users}")
    
    print(f"テストスイート '{suite_config.name}' を開始します...")
    print(f"シナリオ数: {len(suite_config.scenarios)}")
    print(f"テストユーザー数: {suite_config.test_users_count}")
    print(f"New Relic検証: {'有効' if suite_config.verification_enabled else '無効'}")
    print()
    
    try:
        # テストスイートの実行
        results = await test_runner.run_test_suite(suite_config)
        
        # 結果の表示
        print_test_results(results)
        
        # 結果の保存
        if save_results:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"logs/automated_verification_{suite_name}_{timestamp}.json"
            test_runner.save_test_results(results, filename)
        
        # 成功判定
        return results["overall_status"] in ["success", "partial"]
        
    except Exception as e:
        logger.error(f"Test suite execution failed: {e}")
        return False

def print_test_results(results: dict):
    """テスト結果を表示"""
    print("=" * 80)
    print("テスト結果")
    print("=" * 80)
    
    # 全体サマリー
    summary = results.get("summary", {})
    print(f"テストスイート: {results.get('suite_name', 'Unknown')}")
    print(f"全体ステータス: {results.get('overall_status', 'Unknown')}")
    print(f"実行時間: {results.get('duration_seconds', 0):.2f} 秒")
    print()
    
    print("サマリー:")
    print(f"  シナリオ数: {summary.get('total_scenarios', 0)}")
    print(f"  成功: {summary.get('successful_scenarios', 0)}")
    print(f"  部分成功: {summary.get('partial_scenarios', 0)}")
    print(f"  失敗: {summary.get('failed_scenarios', 0)}")
    print(f"  リクエスト成功率: {summary.get('success_rate', 0):.2%}")
    print()
    
    # 各シナリオの結果
    print("シナリオ別結果:")
    print("-" * 60)
    for scenario_result in results.get("scenario_results", []):
        status_icon = {
            "success": "✓",
            "partial": "△", 
            "failed": "✗",
            "error": "✗"
        }.get(scenario_result.get("status", "unknown"), "?")
        
        print(f"{status_icon} {scenario_result.get('scenario_name', 'Unknown')}")
        print(f"    ステータス: {scenario_result.get('status', 'Unknown')}")
        print(f"    実行時間: {scenario_result.get('duration_seconds', 0):.2f} 秒")
        print(f"    成功リクエスト: {scenario_result.get('successful_requests', 0)}/{scenario_result.get('requests_sent', 0)}")
        print(f"    平均レスポンス時間: {scenario_result.get('average_response_time', 0):.2f} ms")
        
        # エラーメッセージがある場合
        error_messages = scenario_result.get("error_messages", [])
        if error_messages:
            print(f"    エラー: {len(error_messages)} 件")
            for i, error in enumerate(error_messages[:3]):  # 最大3件表示
                print(f"      - {error}")
            if len(error_messages) > 3:
                print(f"      ... 他 {len(error_messages) - 3} 件")
        
        print()
    
    # New Relic検証結果
    nr_report = results.get("newrelic_comprehensive_report", {})
    if nr_report:
        print("New Relic検証結果:")
        print("-" * 30)
        
        nr_summary = nr_report.get("summary", {})
        print(f"  分散トレーシング: {'✓' if nr_summary.get('trace_propagation_success') else '✗'}")
        print(f"  Custom Attribute: {'✓' if nr_summary.get('custom_attributes_success') else '✗'}")
        print(f"  パフォーマンス問題: {'✓' if nr_summary.get('performance_scenarios_success') else '✗'}")
        
        # 推奨事項
        recommendations = nr_report.get("recommendations", [])
        if recommendations:
            print("\n  推奨事項:")
            for rec in recommendations:
                print(f"    - {rec}")
        
        print()

async def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description="分散トレーシング自動検証テストスイート",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 基本検証テストを実行
  python run_automated_verification.py basic_verification
  
  # パフォーマンス検証テストを実行
  python run_automated_verification.py performance_verification
  
  # 包括的検証テストを実行
  python run_automated_verification.py comprehensive_verification
  
  # カスタムユーザー数で実行
  python run_automated_verification.py basic_verification --users 10
  
  # 利用可能なテストスイートを表示
  python run_automated_verification.py --list
        """
    )
    
    parser.add_argument(
        "suite_name",
        nargs="?",
        help="実行するテストスイート名"
    )
    
    parser.add_argument(
        "--list",
        action="store_true",
        help="利用可能なテストスイートを表示"
    )
    
    parser.add_argument(
        "--status",
        action="store_true",
        help="システム状態を表示"
    )
    
    parser.add_argument(
        "--users",
        type=int,
        help="テストユーザー数（デフォルト値を上書き）"
    )
    
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="結果をファイルに保存しない"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="詳細ログを表示"
    )
    
    args = parser.parse_args()
    
    # ログレベルの設定
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    print_banner()
    
    # システム状態表示
    if args.status:
        print_system_status()
        return
    
    # テストスイート一覧表示
    if args.list:
        print_available_suites()
        return
    
    # テストスイート名が指定されていない場合
    if not args.suite_name:
        print("エラー: テストスイート名を指定してください。")
        print("利用可能なテストスイート:")
        for suite_name in PREDEFINED_TEST_SUITES.keys():
            print(f"  - {suite_name}")
        print("\n詳細は --list オプションで確認できます。")
        sys.exit(1)
    
    # システム状態の簡易表示
    print_system_status()
    
    # テストスイートの実行
    success = await run_test_suite(
        suite_name=args.suite_name,
        custom_users=args.users,
        save_results=not args.no_save
    )
    
    # 終了コード
    if success:
        print("✓ テストスイートが正常に完了しました。")
        sys.exit(0)
    else:
        print("✗ テストスイートが失敗しました。")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nテストが中断されました。")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)