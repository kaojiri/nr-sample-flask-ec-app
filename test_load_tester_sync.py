#!/usr/bin/env python3
"""
Load Tester側の同期機能テスト
"""
import sys
import os

# Add load-tester directory to path
sys.path.insert(0, './load-tester')

try:
    from user_sync_api import UserSyncAPI, ImportResult
    from datetime import datetime
    
    print('=== Load Tester UserSyncAPI 基本機能テスト ===')
    
    # API初期化
    sync_api = UserSyncAPI()
    print('✓ UserSyncAPI初期化成功')
    
    # テストデータ作成
    test_import_data = {
        "users": [
            {
                "id": 1,
                "username": "testuser1@example.com",
                "email": "testuser1@example.com",
                "password": "TestPass123!",
                "is_test_user": True,
                "test_batch_id": "test_batch_001",
                "created_by_bulk": True
            },
            {
                "id": 2,
                "username": "testuser2@example.com",
                "email": "testuser2@example.com", 
                "password": "TestPass123!",
                "is_test_user": True,
                "test_batch_id": "test_batch_001",
                "created_by_bulk": True
            }
        ],
        "export_timestamp": datetime.utcnow().isoformat(),
        "source_system": "main_application",
        "total_count": 2,
        "metadata": {}
    }
    
    print('✓ テストインポートデータ作成成功')
    
    # インポート機能テスト
    import_result = sync_api.import_users(test_import_data)
    print(f'✓ インポート機能テスト完了:')
    print(f'  - 成功: {import_result.success}')
    print(f'  - インポート数: {import_result.imported_count}')
    print(f'  - 失敗数: {import_result.failed_count}')
    print(f'  - エラー: {import_result.errors}')
    
    # 同期状況取得テスト
    sync_status = sync_api.get_sync_status()
    print(f'✓ 同期状況取得テスト完了:')
    print(f'  - 総ユーザー数: {sync_status.get("total_users", 0)}')
    print(f'  - 最終同期チェック: {sync_status.get("last_sync_check", "N/A")}')
    
    print('✓ Load Tester UserSyncAPI基本機能テスト完了')
    
except Exception as e:
    print(f'✗ テストエラー: {str(e)}')
    import traceback
    traceback.print_exc()