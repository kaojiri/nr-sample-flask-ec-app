#!/usr/bin/env python3
"""
単体テスト統合実行スクリプト
"""
import sys
import os
import subprocess
import time
from datetime import datetime

def run_test_file(test_file):
    """個別のテストファイルを実行"""
    print(f"\n{'='*60}")
    print(f"実行中: {test_file}")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    try:
        # Pythonスクリプトとして実行
        result = subprocess.run(
            [sys.executable, test_file],
            capture_output=True,
            text=True,
            timeout=300  # 5分でタイムアウト
        )
        
        execution_time = time.time() - start_time
        
        # 出力を表示
        if result.stdout:
            print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        
        success = result.returncode == 0
        
        print(f"\n実行時間: {execution_time:.2f}秒")
        print(f"結果: {'✅ 成功' if success else '❌ 失敗'}")
        
        return success, execution_time
        
    except subprocess.TimeoutExpired:
        print(f"❌ タイムアウト: {test_file} (5分)")
        return False, 300
    except Exception as e:
        print(f"❌ 実行エラー: {e}")
        return False, 0


def main():
    """メイン実行"""
    print("単体テスト統合実行開始")
    print(f"開始時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # テストファイルリスト
    test_files = [
        "test_bulk_user_creator.py",
        "test_user_sync_service.py", 
        "test_error_handler.py",
        "test_load_tester_sync_api.py"
    ]
    
    # 既存のテストファイルも含める
    existing_test_files = [
        "test_config_management.py"
    ]
    
    all_test_files = test_files + existing_test_files
    
    # 存在するテストファイルのみを実行
    available_tests = []
    for test_file in all_test_files:
        if os.path.exists(test_file):
            available_tests.append(test_file)
        else:
            print(f"⚠ テストファイルが見つかりません: {test_file}")
    
    if not available_tests:
        print("❌ 実行可能なテストファイルがありません")
        return 1
    
    print(f"\n実行予定のテストファイル ({len(available_tests)}件):")
    for i, test_file in enumerate(available_tests, 1):
        print(f"  {i}. {test_file}")
    
    # 各テストファイルを実行
    results = []
    total_start_time = time.time()
    
    for test_file in available_tests:
        success, execution_time = run_test_file(test_file)
        results.append({
            'file': test_file,
            'success': success,
            'time': execution_time
        })
    
    total_execution_time = time.time() - total_start_time
    
    # 結果サマリー
    print(f"\n{'='*80}")
    print("単体テスト実行結果サマリー")
    print(f"{'='*80}")
    
    passed_count = 0
    failed_count = 0
    
    for result in results:
        status = "✅ PASS" if result['success'] else "❌ FAIL"
        print(f"{result['file']:<35} {status:>10} ({result['time']:.2f}秒)")
        
        if result['success']:
            passed_count += 1
        else:
            failed_count += 1
    
    print(f"\n{'='*80}")
    print(f"総実行時間: {total_execution_time:.2f}秒")
    print(f"成功: {passed_count}件")
    print(f"失敗: {failed_count}件")
    print(f"成功率: {(passed_count / len(results) * 100):.1f}%")
    
    if failed_count == 0:
        print("\n🎉 すべての単体テストが成功しました！")
        return 0
    else:
        print(f"\n⚠ {failed_count}件のテストが失敗しました")
        
        # 失敗したテストの詳細
        print("\n失敗したテスト:")
        for result in results:
            if not result['success']:
                print(f"  - {result['file']}")
        
        return 1


if __name__ == "__main__":
    sys.exit(main())