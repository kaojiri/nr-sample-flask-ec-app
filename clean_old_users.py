#!/usr/bin/env python3
import json
import sys
from pathlib import Path

# Load Testerの設定ファイルから古いユーザーを削除
config_file = Path("data/config.json")

if config_file.exists():
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    test_users = config.get("test_users", [])
    print(f"Before cleanup: {len(test_users)} users")
    
    # 新しいバッチのユーザーのみを保持
    new_batch_id = "693d25b1-9c56-4e66-9d70-2f95cfa1eb89"
    filtered_users = [
        user for user in test_users 
        if user.get("test_batch_id") == new_batch_id
    ]
    
    print(f"After cleanup: {len(filtered_users)} users")
    
    config["test_users"] = filtered_users
    
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    print("✅ Cleanup completed")
else:
    print("❌ Config file not found")