#!/usr/bin/env python3
"""
Load Testerの同期状況を確認するスクリプト
"""
import json
import sys
from pathlib import Path

def check_sync_status():
    """同期状況を確認"""
    print("=== Load Tester 同期状況確認 ===\n")
    
    # 設定ファイルを確認
    config_file = Path("data/config.json")
    if not config_file.exists():
        print("❌ 設定ファイルが見つかりません: data/config.json")
        return
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        test_users = config.get("test_users", [])
        print(f"📊 設定ファイル内のユーザー数: {len(test_users)}")
        
        # ユーザー詳細を表示
        print("\n👥 登録されているユーザー:")
        for i, user in enumerate(test_users, 1):
            user_id = user.get("user_id", "N/A")
            username = user.get("username", "N/A")
            enabled = user.get("enabled", False)
            test_batch_id = user.get("test_batch_id", "N/A")
            is_bulk_created = user.get("is_bulk_created", False)
            
            print(f"  {i}. ID: {user_id}")
            print(f"     ユーザー名: {username}")
            print(f"     有効: {enabled}")
            print(f"     バッチID: {test_batch_id}")
            print(f"     一括作成: {is_bulk_created}")
            print()
        
        # バッチ別の統計
        batch_stats = {}
        for user in test_users:
            batch_id = user.get("test_batch_id", "未設定")
            if batch_id not in batch_stats:
                batch_stats[batch_id] = 0
            batch_stats[batch_id] += 1
        
        print("📈 バッチ別統計:")
        for batch_id, count in batch_stats.items():
            print(f"  {batch_id}: {count}ユーザー")
        
        # 同期関連設定を確認
        bulk_config = config.get("bulk_user_management", {})
        print(f"\n⚙️  同期設定:")
        print(f"  同期有効: {bulk_config.get('sync_enabled', False)}")
        print(f"  自動ログイン: {bulk_config.get('auto_login_on_sync', False)}")
        print(f"  Main App URL: {bulk_config.get('main_app_url', 'N/A')}")
        
    except Exception as e:
        print(f"❌ 設定ファイル読み込みエラー: {e}")

if __name__ == "__main__":
    check_sync_status()