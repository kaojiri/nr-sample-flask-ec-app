#!/usr/bin/env python3
"""
Load Tester側のユーザー同期APIの単体テスト
"""
import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import tempfile
from datetime import datetime

# Load Testerのパスを追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'load-tester'))

def test_import_result_creation():
    """ImportResultクラスの作成とシリアライゼーションをテスト"""
    print("=== ImportResult作成テスト ===")
    
    try:
        from user_sync_api import ImportResult
        
        # ImportResult作成
        import_result = ImportResult(
            success=True,
            imported_count=5,
            failed_count=1,
            errors=["テストエラー"],
            import_timestamp=datetime.utcnow().isoformat()
        )
        
        # 基本属性チェック
        assert import_result.success == True, "successが正しくありません"
        assert import_result.imported_count == 5, "imported_countが正しくありません"
        assert import_result.failed_count == 1, "failed_countが正しくありません"
        assert len(import_result.errors) == 1, "errorsの数が正しくありません"
        
        # 辞書変換テスト
        result_dict = import_result.to_dict()
        assert "success" in result_dict, "辞書にsuccessが含まれていません"
        assert "imported_count" in result_dict, "辞書にimported_countが含まれていません"
        assert result_dict["errors"] == ["テストエラー"], "errorsが正しく変換されていません"
        
        print("✅ ImportResult作成: 成功")
        return True
        
    except Exception as e:
        print(f"❌ ImportResult作成テスト失敗: {e}")
        return False


@patch('user_sync_api.get_user_session_manager')
@patch('user_sync_api.config_manager')
def test_user_sync_api_initialization(mock_config_manager, mock_session_manager):
    """UserSyncAPIの初期化をテスト"""
    print("\n=== UserSyncAPI初期化テスト ===")
    
    try:
        from user_sync_api import UserSyncAPI
        
        # モック設定
        mock_session_manager_instance = Mock()
        mock_session_manager.return_value = mock_session_manager_instance
        
        mock_config = {
            "bulk_user_management": {
                "auto_login_on_sync": True
            }
        }
        mock_config_manager.get_config.return_value = mock_config
        
        # UserSyncAPI初期化
        sync_api = UserSyncAPI()
        
        # 初期化確認
        assert sync_api.session_manager == mock_session_manager_instance, "session_managerが正しく設定されていません"
        assert sync_api.auto_login_enabled == True, "auto_login_enabledが正しく設定されていません"
        
        print("✅ UserSyncAPI初期化: 成功")
        return True
        
    except Exception as e:
        print(f"❌ UserSyncAPI初期化テスト失敗: {e}")
        return False


@patch('user_sync_api.get_user_session_manager')
@patch('user_sync_api.config_manager')
def test_user_sync_api_import_users(mock_config_manager, mock_session_manager):
    """UserSyncAPIのユーザーインポート機能をテスト"""
    print("\n=== UserSyncAPIユーザーインポートテスト ===")
    
    try:
        from user_sync_api import UserSyncAPI, TestUser
        
        # モック設定
        mock_session_manager_instance = Mock()
        mock_session_manager.return_value = mock_session_manager_instance
        mock_session_manager_instance.update_test_users_config.return_value = True
        mock_session_manager_instance.get_test_users.return_value = []
        
        mock_config = {
            "bulk_user_management": {
                "auto_login_on_sync": False  # 自動ログインを無効にしてテストを簡素化
            }
        }
        mock_config_manager.get_config.return_value = mock_config
        
        # テストデータ作成
        user_data = {
            "users": [
                {
                    "id": 1,
                    "username": "testuser1@example.com",
                    "password": "TestPass123!",
                    "test_batch_id": "batch_001"
                },
                {
                    "id": 2,
                    "username": "testuser2@example.com",
                    "password": "TestPass123!",
                    "test_batch_id": "batch_001"
                }
            ],
            "export_timestamp": datetime.utcnow().isoformat(),
            "source_system": "main_application",
            "total_count": 2
        }
        
        # UserSyncAPI初期化とインポート実行
        sync_api = UserSyncAPI()
        result = sync_api.import_users(user_data)
        
        # 結果検証
        assert result.success == True, f"インポートが失敗しました: {result.errors}"
        assert result.imported_count == 2, f"インポート数が正しくありません: {result.imported_count}"
        assert result.failed_count == 0, f"失敗数が0でありません: {result.failed_count}"
        
        # session_managerのメソッドが呼ばれたかチェック
        mock_session_manager_instance.update_test_users_config.assert_called_once()
        mock_session_manager_instance.reload_test_users.assert_called_once()
        
        print("✅ UserSyncAPIユーザーインポート: 成功")
        return True
        
    except Exception as e:
        print(f"❌ UserSyncAPIユーザーインポートテスト失敗: {e}")
        return False


@patch('user_sync_api.get_user_session_manager')
@patch('user_sync_api.config_manager')
def test_user_sync_api_import_error_handling(mock_config_manager, mock_session_manager):
    """UserSyncAPIのインポートエラーハンドリングをテスト"""
    print("\n=== UserSyncAPIインポートエラーハンドリングテスト ===")
    
    try:
        from user_sync_api import UserSyncAPI
        
        # モック設定（設定更新が失敗するように）
        mock_session_manager_instance = Mock()
        mock_session_manager.return_value = mock_session_manager_instance
        mock_session_manager_instance.update_test_users_config.return_value = False  # 失敗
        mock_session_manager_instance.get_test_users.return_value = []
        
        mock_config = {
            "bulk_user_management": {
                "auto_login_on_sync": False
            }
        }
        mock_config_manager.get_config.return_value = mock_config
        
        # 無効なテストデータ
        invalid_user_data = {
            "users": [
                {
                    "id": 1,
                    # usernameが欠落
                    "password": "TestPass123!"
                }
            ],
            "total_count": 1
        }
        
        # UserSyncAPI初期化とインポート実行
        sync_api = UserSyncAPI()
        result = sync_api.import_users(invalid_user_data)
        
        # エラー結果検証
        assert result.success == False, "エラー時にsuccessがTrueになっています"
        assert result.imported_count == 0, "エラー時にimported_countが0でありません"
        assert len(result.errors) > 0, "エラーが記録されていません"
        
        print("✅ UserSyncAPIインポートエラーハンドリング: 成功")
        return True
        
    except Exception as e:
        print(f"❌ UserSyncAPIインポートエラーハンドリングテスト失敗: {e}")
        return False


@patch('user_sync_api.get_user_session_manager')
@patch('user_sync_api.config_manager')
def test_user_sync_api_sync_status(mock_config_manager, mock_session_manager):
    """UserSyncAPIの同期状況取得をテスト"""
    print("\n=== UserSyncAPI同期状況取得テスト ===")
    
    try:
        from user_sync_api import UserSyncAPI, TestUser
        
        # モックTestUserオブジェクト作成
        mock_test_user1 = TestUser(
            user_id="user1",
            username="testuser1@example.com",
            password="TestPass123!",
            enabled=True,
            description="Test user 1"
        )
        
        mock_test_user2 = TestUser(
            user_id="user2",
            username="testuser2@example.com",
            password="TestPass123!",
            enabled=False,
            description="Test user 2"
        )
        
        # モック設定
        mock_session_manager_instance = Mock()
        mock_session_manager.return_value = mock_session_manager_instance
        mock_session_manager_instance.get_test_users.return_value = [mock_test_user1, mock_test_user2]
        
        # モックセッション統計
        mock_session_stats = Mock()
        mock_session_stats.to_dict.return_value = {
            "active_sessions": 1,
            "total_sessions": 2,
            "success_rate": 50.0
        }
        mock_session_manager_instance.get_session_stats.return_value = mock_session_stats
        
        mock_config = {
            "bulk_user_management": {
                "auto_login_on_sync": True
            }
        }
        mock_config_manager.get_config.return_value = mock_config
        
        # UserSyncAPI初期化と同期状況取得
        sync_api = UserSyncAPI()
        status = sync_api.get_sync_status()
        
        # 結果検証
        assert "total_users" in status, "同期状況にtotal_usersが含まれていません"
        assert status["total_users"] == 2, f"total_usersが正しくありません: {status['total_users']}"
        assert "users" in status, "同期状況にusersが含まれていません"
        assert len(status["users"]) == 2, "usersの数が正しくありません"
        assert "session_stats" in status, "同期状況にsession_statsが含まれていません"
        
        # ユーザー情報の詳細チェック
        user_info = status["users"][0]
        assert "user_id" in user_info, "ユーザー情報にuser_idが含まれていません"
        assert "username" in user_info, "ユーザー情報にusernameが含まれていません"
        assert "enabled" in user_info, "ユーザー情報にenabledが含まれていません"
        
        print("✅ UserSyncAPI同期状況取得: 成功")
        return True
        
    except Exception as e:
        print(f"❌ UserSyncAPI同期状況取得テスト失敗: {e}")
        return False


@patch('user_sync_api.get_user_session_manager')
@patch('user_sync_api.config_manager')
@patch('user_sync_api.asyncio')
def test_user_sync_api_bulk_login(mock_asyncio, mock_config_manager, mock_session_manager):
    """UserSyncAPIの一括ログイン機能をテスト"""
    print("\n=== UserSyncAPI一括ログインテスト ===")
    
    try:
        from user_sync_api import UserSyncAPI
        
        # モック設定
        mock_session_manager_instance = Mock()
        mock_session_manager.return_value = mock_session_manager_instance
        
        # モックセッション作成
        mock_session1 = Mock()
        mock_session1.user_id = "user1"
        mock_session1.username = "testuser1@example.com"
        mock_session1.login_time = datetime.utcnow()
        mock_session1.is_valid = True
        
        mock_session2 = Mock()
        mock_session2.user_id = "user2"
        mock_session2.username = "testuser2@example.com"
        mock_session2.login_time = datetime.utcnow()
        mock_session2.is_valid = True
        
        mock_sessions = {
            "user1": mock_session1,
            "user2": mock_session2
        }
        
        # 非同期ループのモック
        mock_loop = Mock()
        mock_loop.run_until_complete.return_value = mock_sessions
        mock_asyncio.new_event_loop.return_value = mock_loop
        
        mock_config = {
            "bulk_user_management": {
                "auto_login_on_sync": True
            }
        }
        mock_config_manager.get_config.return_value = mock_config
        
        # UserSyncAPI初期化と一括ログイン実行
        sync_api = UserSyncAPI()
        result = sync_api.bulk_login_users()
        
        # 結果検証
        assert result["success"] == True, f"一括ログインが失敗しました: {result.get('error')}"
        assert result["logged_in_count"] == 2, f"ログイン数が正しくありません: {result['logged_in_count']}"
        assert "sessions" in result, "結果にsessionsが含まれていません"
        assert len(result["sessions"]) == 2, "sessionsの数が正しくありません"
        
        # セッション情報の詳細チェック
        session_info = result["sessions"][0]
        assert "user_id" in session_info, "セッション情報にuser_idが含まれていません"
        assert "username" in session_info, "セッション情報にusernameが含まれていません"
        assert "login_time" in session_info, "セッション情報にlogin_timeが含まれていません"
        assert "is_valid" in session_info, "セッション情報にis_validが含まれていません"
        
        print("✅ UserSyncAPI一括ログイン: 成功")
        return True
        
    except Exception as e:
        print(f"❌ UserSyncAPI一括ログインテスト失敗: {e}")
        return False


@patch('user_sync_api.get_user_session_manager')
@patch('user_sync_api.config_manager')
def test_user_sync_api_batch_operations(mock_config_manager, mock_session_manager):
    """UserSyncAPIのバッチ操作をテスト"""
    print("\n=== UserSyncAPIバッチ操作テスト ===")
    
    try:
        from user_sync_api import UserSyncAPI
        
        # モック設定
        mock_session_manager_instance = Mock()
        mock_session_manager.return_value = mock_session_manager_instance
        
        # バッチ情報のモック
        mock_batches = ["batch_001", "batch_002"]
        mock_session_manager_instance.get_all_batches.return_value = mock_batches
        
        mock_batch_stats = {
            "batch_id": "batch_001",
            "user_count": 5,
            "active_sessions": 3,
            "total_sessions": 5
        }
        mock_session_manager_instance.get_batch_session_stats.return_value = mock_batch_stats
        
        mock_config = {
            "bulk_user_management": {
                "auto_login_on_sync": True
            }
        }
        mock_config_manager.get_config.return_value = mock_config
        
        # UserSyncAPI初期化
        sync_api = UserSyncAPI()
        
        # バッチ情報取得テスト
        batch_info = sync_api.get_batch_info()
        
        assert batch_info["total_batches"] == 2, f"バッチ数が正しくありません: {batch_info['total_batches']}"
        assert "batches" in batch_info, "バッチ情報にbatchesが含まれていません"
        
        print("✅ バッチ情報取得: 成功")
        
        # バッチ削除テスト
        mock_session_manager_instance.remove_batch_users.return_value = 3
        mock_session_manager_instance.get_test_users.return_value = []
        mock_session_manager_instance.update_test_users_config.return_value = True
        
        remove_result = sync_api.remove_batch("batch_001")
        
        assert remove_result["success"] == True, "バッチ削除が失敗しました"
        assert remove_result["batch_id"] == "batch_001", "バッチIDが正しくありません"
        assert remove_result["removed_count"] == 3, "削除数が正しくありません"
        
        print("✅ バッチ削除: 成功")
        
        return True
        
    except Exception as e:
        print(f"❌ UserSyncAPIバッチ操作テスト失敗: {e}")
        return False


@patch('user_sync_api.get_user_session_manager')
@patch('user_sync_api.config_manager')
def test_user_sync_api_cleanup_operations(mock_config_manager, mock_session_manager):
    """UserSyncAPIのクリーンアップ操作をテスト"""
    print("\n=== UserSyncAPIクリーンアップ操作テスト ===")
    
    try:
        from user_sync_api import UserSyncAPI, TestUser
        
        # モック設定
        mock_session_manager_instance = Mock()
        mock_session_manager.return_value = mock_session_manager_instance
        
        # テストユーザーのモック
        mock_test_users = [
            TestUser("user1", "testuser1@example.com", "pass", True, "Test user 1"),
            TestUser("user2", "testuser2@example.com", "pass", True, "Test user 2")
        ]
        mock_session_manager_instance.get_test_users.return_value = mock_test_users
        
        mock_config = {
            "bulk_user_management": {
                "auto_login_on_sync": True
            }
        }
        mock_config_manager.get_config.return_value = mock_config
        
        # UserSyncAPI初期化
        sync_api = UserSyncAPI()
        
        # 全ユーザークリーンアップテスト
        result = sync_api.cleanup_all_test_users()
        
        assert result["success"] == True, f"クリーンアップが失敗しました: {result.get('error')}"
        assert result["removed_count"] == 2, f"削除数が正しくありません: {result['removed_count']}"
        assert result["cleanup_type"] == "all_users", "クリーンアップタイプが正しくありません"
        
        print("✅ 全ユーザークリーンアップ: 成功")
        
        # クリーンアップ候補取得テスト
        mock_session_manager_instance.get_all_batches.return_value = ["batch_001", "batch_002"]
        mock_batch_stats = {
            "batch_id": "batch_001",
            "active_sessions": 2,
            "total_sessions": 5
        }
        mock_session_manager_instance.get_batch_session_stats.return_value = mock_batch_stats
        
        candidates = sync_api.get_cleanup_candidates(age_days=7)
        
        assert "total_batches" in candidates, "候補情報にtotal_batchesが含まれていません"
        assert "candidates" in candidates, "候補情報にcandidatesが含まれていません"
        assert candidates["age_threshold_days"] == 7, "年齢閾値が正しくありません"
        
        print("✅ クリーンアップ候補取得: 成功")
        
        return True
        
    except Exception as e:
        print(f"❌ UserSyncAPIクリーンアップ操作テスト失敗: {e}")
        return False


def test_load_tester_error_handler():
    """Load Tester用エラーハンドラーをテスト"""
    print("\n=== Load Testerエラーハンドラーテスト ===")
    
    try:
        from user_sync_api import LoadTesterErrorHandler
        
        # 一時ログディレクトリ
        with tempfile.TemporaryDirectory() as temp_dir:
            error_handler = LoadTesterErrorHandler()
            original_log_file = error_handler.error_log_file
            error_handler.error_log_file = os.path.join(temp_dir, "test_load_tester_errors.log")
            
            try:
                # エラーログテスト
                test_error = ValueError("Load Testerテストエラー")
                context = {"operation": "test_import", "user_count": 5}
                
                error_handler.log_error("import_users", test_error, context)
                
                # ログファイル確認
                assert os.path.exists(error_handler.error_log_file), "ログファイルが作成されていません"
                
                with open(error_handler.error_log_file, 'r', encoding='utf-8') as f:
                    log_content = f.read()
                
                assert "Load Testerテストエラー" in log_content, "エラーメッセージがログに記録されていません"
                assert "import_users" in log_content, "操作名がログに記録されていません"
                assert "test_import" in log_content, "コンテキストがログに記録されていません"
                
                print("✅ Load Testerエラーログ: 成功")
                
                # エラーハンドリング付き実行テスト
                def test_function():
                    return "成功"
                
                result = error_handler.with_error_handling("test_operation", test_function)
                assert result == "成功", "エラーハンドリング付き実行の結果が正しくありません"
                
                print("✅ Load Testerエラーハンドリング付き実行: 成功")
                
            finally:
                error_handler.error_log_file = original_log_file
        
        return True
        
    except Exception as e:
        print(f"❌ Load Testerエラーハンドラーテスト失敗: {e}")
        return False


def main():
    """メインテスト実行"""
    print("Load Tester側ユーザー同期APIの単体テスト開始")
    print("=" * 50)
    
    tests = [
        test_import_result_creation,
        test_user_sync_api_initialization,
        test_user_sync_api_import_users,
        test_user_sync_api_import_error_handling,
        test_user_sync_api_sync_status,
        test_user_sync_api_bulk_login,
        test_user_sync_api_batch_operations,
        test_user_sync_api_cleanup_operations,
        test_load_tester_error_handler
    ]
    
    passed = 0
    total = len(tests)
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ テスト実行エラー {test_func.__name__}: {e}")
    
    print("\n" + "=" * 50)
    print(f"Load Tester同期API テスト結果: {passed}/{total} 成功")
    
    if passed == total:
        print("✅ すべてのテストが成功しました！")
        return True
    else:
        print("❌ 一部のテストが失敗しました")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)