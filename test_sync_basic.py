#!/usr/bin/env python3
"""
ユーザー同期機能の基本テスト
"""
import sys
import os

# Add app directory to path
sys.path.insert(0, './app')

try:
    from services.user_sync_service import UserSyncService, TestUserData, UserExportData
    from datetime import datetime
    
    print('=== UserSyncService 基本機能テスト ===')
    
    # サービス初期化
    sync_service = UserSyncService('http://localhost:8080')
    print('✓ UserSyncService初期化成功')
    
    # テストデータ作成
    test_users = [
        TestUserData(
            id=1,
            username='testuser1@example.com',
            email='testuser1@example.com',
            password='TestPass123!',
            test_batch_id='test_batch_001'
        ),
        TestUserData(
            id=2,
            username='testuser2@example.com', 
            email='testuser2@example.com',
            password='TestPass123!',
            test_batch_id='test_batch_001'
        )
    ]
    
    export_data = UserExportData(
        users=test_users,
        export_timestamp=datetime.utcnow().isoformat(),
        source_system='test_system',
        total_count=len(test_users)
    )
    
    print('✓ テストデータ作成成功')
    
    # JSON変換テスト
    json_data = export_data.to_dict()
    print(f'✓ JSON変換成功: {len(json_data["users"])}件のユーザー')
    
    # データ構造確認
    print(f'✓ エクスポートデータ構造確認:')
    print(f'  - ソースシステム: {json_data["source_system"]}')
    print(f'  - 総数: {json_data["total_count"]}')
    print(f'  - エクスポート時刻: {json_data["export_timestamp"]}')
    
    print('✓ UserSyncService基本機能テスト完了')
    
except Exception as e:
    print(f'✗ テストエラー: {str(e)}')
    import traceback
    traceback.print_exc()