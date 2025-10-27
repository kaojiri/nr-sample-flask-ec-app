#!/usr/bin/env python3
"""
UserSyncServiceクラスの単体テスト
"""
import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import tempfile
from datetime import datetime

# アプリケーションのパスを追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

def test_test_user_data_creation():
    """TestUserDataクラスの作成とシリアライゼーションをテスト"""
    print("=== TestUserData作成テスト ===")
    
    try:
        from app.services.user_sync_service import TestUserData
        
        # TestUserData作成
        test_user = TestUserData(
            id=1,
            username="testuser@example.com",
            email="testuser@example.com",
            password="TestPass123!",
            test_batch_id="batch_001"
        )
        
        # 基本属性チェック
        assert test_user.id == 1, "IDが正しくありません"
        assert test_user.username == "testuser@example.com", "ユーザー名が正しくありません"
        assert test_user.is_test_user == True, "is_test_userがデフォルト値になっていません"
        
        # 辞書変換テスト
        user_dict = test_user.to_dict()
        assert "id" in user_dict, "辞書にIDが含まれていません"
        assert "username" in user_dict, "辞書にユーザー名が含まれていません"
        assert user_dict["test_batch_id"] == "batch_001", "バッチIDが正しくありません"
        
        print("✅ TestUserData作成: 成功")
        return True
        
    except Exception as e:
        print(f"❌ TestUserData作成テスト失敗: {e}")
        return False


def test_user_export_data_serialization():
    """UserExportDataのシリアライゼーションをテスト"""
    print("\n=== UserExportDataシリアライゼーションテスト ===")
    
    try:
        from app.services.user_sync_service import UserExportData, TestUserData
        
        # テストユーザーデータ作成
        test_users = [
            TestUserData(
                id=1,
                username="user1@example.com",
                email="user1@example.com",
                test_batch_id="batch_001"
            ),
            TestUserData(
                id=2,
                username="user2@example.com",
                email="user2@example.com",
                test_batch_id="batch_001"
            )
        ]
        
        # エクスポートデータ作成
        export_data = UserExportData(
            users=test_users,
            export_timestamp=datetime.utcnow().isoformat(),
            source_system="test_system",
            total_count=len(test_users),
            metadata={"test": "metadata"}
        )
        
        # 辞書変換テスト
        export_dict = export_data.to_dict()
        assert "users" in export_dict, "辞書にusersが含まれていません"
        assert len(export_dict["users"]) == 2, "ユーザー数が正しくありません"
        assert export_dict["total_count"] == 2, "total_countが正しくありません"
        
        # 辞書からの復元テスト
        restored_data = UserExportData.from_dict(export_dict)
        assert len(restored_data.users) == 2, "復元されたユーザー数が正しくありません"
        assert restored_data.source_system == "test_system", "source_systemが正しくありません"
        
        print("✅ UserExportDataシリアライゼーション: 成功")
        return True
        
    except Exception as e:
        print(f"❌ UserExportDataシリアライゼーションテスト失敗: {e}")
        return False


@patch('app.services.user_sync_service.User')
@patch('app.services.user_sync_service.db')
def test_user_sync_service_export(mock_db, mock_user):
    """UserSyncServiceのエクスポート機能をテスト"""
    print("\n=== UserSyncServiceエクスポートテスト ===")
    
    try:
        from app.services.user_sync_service import UserSyncService
        
        # モックユーザーデータ設定
        mock_user_obj1 = Mock()
        mock_user_obj1.id = 1
        mock_user_obj1.username = "testuser1@example.com"
        mock_user_obj1.email = "testuser1@example.com"
        mock_user_obj1.is_test_user = True
        mock_user_obj1.test_batch_id = "batch_001"
        mock_user_obj1.created_by_bulk = True
        mock_user_obj1.created_at = datetime.utcnow()
        
        mock_user_obj2 = Mock()
        mock_user_obj2.id = 2
        mock_user_obj2.username = "testuser2@example.com"
        mock_user_obj2.email = "testuser2@example.com"
        mock_user_obj2.is_test_user = True
        mock_user_obj2.test_batch_id = "batch_001"
        mock_user_obj2.created_by_bulk = True
        mock_user_obj2.created_at = datetime.utcnow()
        
        # クエリモック設定
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [mock_user_obj1, mock_user_obj2]
        mock_user.query = mock_query
        
        # UserSyncService初期化
        sync_service = UserSyncService("http://test-load-tester:8080")
        
        # エクスポート実行
        export_data = sync_service.export_users_from_app({"test_users_only": True})
        
        # 結果検証
        assert export_data.total_count == 2, f"エクスポート数が正しくありません: {export_data.total_count}"
        assert len(export_data.users) == 2, f"ユーザー数が正しくありません: {len(export_data.users)}"
        assert export_data.source_system == "main_application", "source_systemが正しくありません"
        
        # ユーザーデータ検証
        user1 = export_data.users[0]
        assert user1.username == "testuser1@example.com", "ユーザー1のユーザー名が正しくありません"
        assert user1.test_batch_id == "batch_001", "ユーザー1のバッチIDが正しくありません"
        
        print("✅ UserSyncServiceエクスポート: 成功")
        return True
        
    except Exception as e:
        print(f"❌ UserSyncServiceエクスポートテスト失敗: {e}")
        return False


@patch('app.services.user_sync_service.requests')
def test_user_sync_service_import(mock_requests):
    """UserSyncServiceのインポート機能をテスト"""
    print("\n=== UserSyncServiceインポートテスト ===")
    
    try:
        from app.services.user_sync_service import UserSyncService, UserExportData, TestUserData
        
        # モックレスポンス設定
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "imported_count": 2,
            "errors": []
        }
        mock_requests.post.return_value = mock_response
        
        # テストデータ作成
        test_users = [
            TestUserData(
                id=1,
                username="testuser1@example.com",
                email="testuser1@example.com",
                test_batch_id="batch_001"
            ),
            TestUserData(
                id=2,
                username="testuser2@example.com",
                email="testuser2@example.com",
                test_batch_id="batch_001"
            )
        ]
        
        export_data = UserExportData(
            users=test_users,
            export_timestamp=datetime.utcnow().isoformat(),
            source_system="test_system",
            total_count=len(test_users)
        )
        
        # UserSyncService初期化
        sync_service = UserSyncService("http://test-load-tester:8080")
        
        # インポート実行
        sync_result = sync_service.import_users_to_load_tester(export_data)
        
        # 結果検証
        assert sync_result.success == True, "インポートが失敗しました"
        assert sync_result.synced_count == 2, f"同期数が正しくありません: {sync_result.synced_count}"
        assert len(sync_result.errors) == 0, f"エラーが発生しました: {sync_result.errors}"
        
        # HTTPリクエストが正しく呼ばれたかチェック
        mock_requests.post.assert_called_once()
        call_args = mock_requests.post.call_args
        assert "http://test-load-tester:8080/api/users/import" in call_args[0], "正しいURLが呼ばれていません"
        
        print("✅ UserSyncServiceインポート: 成功")
        return True
        
    except Exception as e:
        print(f"❌ UserSyncServiceインポートテスト失敗: {e}")
        return False


@patch('app.services.user_sync_service.requests')
def test_user_sync_service_import_error_handling(mock_requests):
    """UserSyncServiceのインポートエラーハンドリングをテスト"""
    print("\n=== UserSyncServiceインポートエラーハンドリングテスト ===")
    
    try:
        from app.services.user_sync_service import UserSyncService, UserExportData, TestUserData
        import requests
        
        # エラーレスポンス設定
        mock_requests.post.side_effect = requests.exceptions.ConnectionError("接続エラー")
        
        # テストデータ作成
        test_users = [
            TestUserData(
                id=1,
                username="testuser1@example.com",
                email="testuser1@example.com"
            )
        ]
        
        export_data = UserExportData(
            users=test_users,
            export_timestamp=datetime.utcnow().isoformat(),
            source_system="test_system",
            total_count=len(test_users)
        )
        
        # UserSyncService初期化
        sync_service = UserSyncService("http://test-load-tester:8080")
        
        # インポート実行（エラーが発生するはず）
        sync_result = sync_service.import_users_to_load_tester(export_data)
        
        # エラー結果検証
        assert sync_result.success == False, "エラー時にsuccessがTrueになっています"
        assert sync_result.synced_count == 0, "エラー時に同期数が0でありません"
        assert len(sync_result.errors) > 0, "エラーが記録されていません"
        
        print("✅ UserSyncServiceインポートエラーハンドリング: 成功")
        return True
        
    except Exception as e:
        print(f"❌ UserSyncServiceインポートエラーハンドリングテスト失敗: {e}")
        return False


def test_user_sync_service_json_file_operations():
    """UserSyncServiceのJSONファイル操作をテスト"""
    print("\n=== UserSyncServiceJSONファイル操作テスト ===")
    
    try:
        from app.services.user_sync_service import UserSyncService
        
        # 一時ファイル作成
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_file = f.name
        
        try:
            # UserSyncService初期化（モック環境）
            with patch('app.services.user_sync_service.User') as mock_user:
                # モックユーザーデータ設定
                mock_user_obj = Mock()
                mock_user_obj.id = 1
                mock_user_obj.username = "testuser@example.com"
                mock_user_obj.email = "testuser@example.com"
                mock_user_obj.is_test_user = True
                mock_user_obj.test_batch_id = "batch_001"
                mock_user_obj.created_by_bulk = True
                mock_user_obj.created_at = datetime.utcnow()
                
                mock_query = Mock()
                mock_query.filter.return_value = mock_query
                mock_query.all.return_value = [mock_user_obj]
                mock_user.query = mock_query
                
                sync_service = UserSyncService("http://test-load-tester:8080")
                
                # JSONファイルエクスポートテスト
                success = sync_service.export_to_json_file(temp_file, {"test_users_only": True})
                assert success == True, "JSONファイルエクスポートが失敗しました"
                
                # ファイル内容確認
                assert os.path.exists(temp_file), "エクスポートファイルが作成されていません"
                
                with open(temp_file, 'r', encoding='utf-8') as f:
                    file_data = json.load(f)
                
                assert "users" in file_data, "ファイルにusersが含まれていません"
                assert file_data["total_count"] == 1, "ファイルのtotal_countが正しくありません"
                
                print("✅ JSONファイルエクスポート: 成功")
                
                # JSONファイルインポートテスト（モック使用）
                with patch('app.services.user_sync_service.requests') as mock_requests:
                    mock_response = Mock()
                    mock_response.status_code = 200
                    mock_response.json.return_value = {
                        "success": True,
                        "imported_count": 1,
                        "errors": []
                    }
                    mock_requests.post.return_value = mock_response
                    
                    import_result = sync_service.import_from_json_file(temp_file)
                    assert import_result.success == True, "JSONファイルインポートが失敗しました"
                    
                    print("✅ JSONファイルインポート: 成功")
        
        finally:
            # クリーンアップ
            try:
                os.unlink(temp_file)
            except:
                pass
        
        return True
        
    except Exception as e:
        print(f"❌ UserSyncServiceJSONファイル操作テスト失敗: {e}")
        return False


@patch('app.services.user_sync_service.User')
@patch('app.services.user_sync_service.requests')
def test_user_sync_service_validation(mock_requests, mock_user):
    """UserSyncServiceの整合性検証機能をテスト"""
    print("\n=== UserSyncService整合性検証テスト ===")
    
    try:
        from app.services.user_sync_service import UserSyncService
        
        # Main Appモックユーザー設定
        mock_user_obj = Mock()
        mock_user_obj.username = "testuser@example.com"
        
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [mock_user_obj]
        mock_user.query = mock_query
        
        # Load Testerレスポンス設定
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "users": [
                {"username": "testuser@example.com"}
            ]
        }
        mock_requests.get.return_value = mock_response
        
        sync_service = UserSyncService("http://test-load-tester:8080")
        
        # 整合性検証実行
        validation_result = sync_service.validate_sync_integrity()
        
        # 結果検証
        assert validation_result.is_valid == True, "整合性検証が失敗しました"
        assert validation_result.total_checked == 1, "検証数が正しくありません"
        assert len(validation_result.inconsistencies) == 0, "不整合が検出されました"
        
        print("✅ UserSyncService整合性検証: 成功")
        return True
        
    except Exception as e:
        print(f"❌ UserSyncService整合性検証テスト失敗: {e}")
        return False


def main():
    """メインテスト実行"""
    print("UserSyncServiceクラスの単体テスト開始")
    print("=" * 50)
    
    tests = [
        test_test_user_data_creation,
        test_user_export_data_serialization,
        test_user_sync_service_export,
        test_user_sync_service_import,
        test_user_sync_service_import_error_handling,
        test_user_sync_service_json_file_operations,
        test_user_sync_service_validation
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
    print(f"UserSyncService テスト結果: {passed}/{total} 成功")
    
    if passed == total:
        print("✅ すべてのテストが成功しました！")
        return True
    else:
        print("❌ 一部のテストが失敗しました")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)