#!/usr/bin/env python3
"""
New Relic検証機能の簡単なテストスクリプト（依存関係最小限）
"""
import json
import os
import sys
from datetime import datetime

def test_config_structure():
    """設定ファイルの構造をテスト"""
    print("=" * 60)
    print("設定ファイル構造テスト")
    print("=" * 60)
    
    config_file = "load-tester/data/config.json"
    
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        # New Relic検証設定の確認
        if "newrelic_verification" in config:
            nr_config = config["newrelic_verification"]
            print("✅ New Relic検証設定が存在します")
            print(f"   - 有効: {nr_config.get('enabled', False)}")
            print(f"   - 監視対象アプリ: {nr_config.get('app_names', [])}")
            print(f"   - タイムアウト: {nr_config.get('verification_timeout_seconds', 300)}秒")
            print(f"   - リトライ回数: {nr_config.get('retry_attempts', 3)}")
        else:
            print("❌ New Relic検証設定が見つかりません")
            return False
        
        # 分散サービス設定の確認
        if "distributed_service" in config:
            ds_config = config["distributed_service"]
            print("✅ 分散サービス設定が存在します")
            print(f"   - ベースURL: {ds_config.get('base_url', 'N/A')}")
            print(f"   - エンドポイント数: {len(ds_config.get('endpoints', {}))}")
            print(f"   - テストシナリオ数: {len(ds_config.get('test_scenarios', {}))}")
        else:
            print("❌ 分散サービス設定が見つかりません")
            return False
        
        return True
        
    except FileNotFoundError:
        print(f"❌ 設定ファイルが見つかりません: {config_file}")
        return False
    except json.JSONDecodeError as e:
        print(f"❌ 設定ファイルのJSON解析エラー: {e}")
        return False
    except Exception as e:
        print(f"❌ 設定ファイル読み込みエラー: {e}")
        return False

def test_file_structure():
    """実装ファイルの存在確認"""
    print("\n" + "=" * 60)
    print("実装ファイル構造テスト")
    print("=" * 60)
    
    required_files = [
        "load-tester/newrelic_verification.py",
        "load-tester/automated_test_scenarios.py", 
        "load-tester/run_automated_verification.py",
        "load-tester/distributed_service_client.py"
    ]
    
    all_exist = True
    
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} が見つかりません")
            all_exist = False
    
    return all_exist

def test_environment_variables():
    """環境変数の確認"""
    print("\n" + "=" * 60)
    print("環境変数テスト")
    print("=" * 60)
    
    env_vars = [
        "NEW_RELIC_API_KEY",
        "NEW_RELIC_ACCOUNT_ID"
    ]
    
    all_set = True
    
    for var in env_vars:
        value = os.getenv(var)
        if value:
            if value.startswith("${"):
                print(f"⚠️  {var}: プレースホルダー値 ({value})")
                all_set = False  # プレースホルダーは未設定扱い
            else:
                print(f"✅ {var}: 設定済み (***)")
        else:
            print(f"❌ {var}: 未設定")
            all_set = False
    
    if all_set:
        print("\n✅ すべての環境変数が正しく設定されています")
    else:
        print("\n❌ 一部の環境変数が未設定です")
        print("注意: New Relic検証機能を使用するには、上記の環境変数を設定する必要があります")
    
    return all_set

def test_code_syntax():
    """実装ファイルの構文チェック"""
    print("\n" + "=" * 60)
    print("コード構文テスト")
    print("=" * 60)
    
    python_files = [
        "load-tester/newrelic_verification.py",
        "load-tester/automated_test_scenarios.py",
        "load-tester/run_automated_verification.py"
    ]
    
    all_valid = True
    
    for file_path in python_files:
        try:
            with open(file_path, 'r') as f:
                code = f.read()
            
            # 基本的な構文チェック
            compile(code, file_path, 'exec')
            print(f"✅ {file_path}: 構文OK")
            
        except SyntaxError as e:
            print(f"❌ {file_path}: 構文エラー - {e}")
            all_valid = False
        except FileNotFoundError:
            print(f"❌ {file_path}: ファイルが見つかりません")
            all_valid = False
        except Exception as e:
            print(f"⚠️  {file_path}: チェックエラー - {e}")
    
    return all_valid

def main():
    """メイン関数"""
    print("New Relic検証機能 - 簡単テストスイート")
    print(f"実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    test_results = []
    
    # 1. 設定ファイル構造テスト
    config_ok = test_config_structure()
    test_results.append(("設定ファイル構造", config_ok))
    
    # 2. ファイル構造テスト
    files_ok = test_file_structure()
    test_results.append(("実装ファイル構造", files_ok))
    
    # 3. 環境変数テスト
    env_ok = test_environment_variables()
    test_results.append(("環境変数", env_ok))
    
    # 4. コード構文テスト
    syntax_ok = test_code_syntax()
    test_results.append(("コード構文", syntax_ok))
    
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
        print("\n次のステップ:")
        print("1. 必要な依存関係をインストール: pip install -r load-tester/requirements.txt")
        print("2. New Relic環境変数を設定")
        print("3. 分散サービスとメインアプリケーションを起動")
        print("4. 完全なテストを実行: python3 load-tester/run_automated_verification.py basic_verification")
        return 0
    elif passed_tests > 0:
        print("⚠️  一部のテストが失敗しました")
        return 1
    else:
        print("❌ すべてのテストが失敗しました")
        return 2

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nテストが中断されました")
        sys.exit(1)
    except Exception as e:
        print(f"予期しないエラー: {e}")
        sys.exit(1)