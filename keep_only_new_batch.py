#!/usr/bin/env python3
import json
from pathlib import Path

# 新しいバッチのみを保持
new_batch_id = "c35939c3-992f-4ee6-8931-f7823502ab60"
config_file = Path("data/config.json")

if config_file.exists():
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    test_users = config.get("test_users", [])
    print(f"Before cleanup: {len(test_users)} users")
    
    # 新しいバッチのユーザーのみを保持
    filtered_users = [
        user for user in test_users 
        if user.get("test_batch_id") == new_batch_id
    ]
    
    print(f"After cleanup: {len(filtered_users)} users")
    print("Kept users:")
    for user in filtered_users:
        print(f"  - {user.get('username')} (ID: {user.get('user_id')})")
    
    config["test_users"] = filtered_users
    
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    print("✅ Cleanup completed")
else:
    print("❌ Config file not found")