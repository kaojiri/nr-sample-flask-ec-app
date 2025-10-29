#!/usr/bin/env python3
import requests
import json
import time

# 新しいバッチでユーザーを作成
create_data = {
    "config": {
        "username_pattern": "testuser_fix_{id}@example.com",
        "password": "TestPass123!",
        "email_domain": "example.com",
        "batch_size": 3,
        "max_users_per_batch": 3,
        "user_role": "user",
        "custom_attributes": {}
    }
}

print("Creating new batch of users...")
response = requests.post(
    "http://localhost:5001/api/bulk-users/create",
    json=create_data,
    timeout=30
)

if response.status_code == 200:
    result = response.json()
    print(f"✅ Created {result.get('created_count', 0)} users")
    batch_id = result.get('batch_id')
    print(f"Batch ID: {batch_id}")
    
    # 同期実行
    print("\nSyncing to Load Tester...")
    sync_data = {
        "sync_all": True,
        "auto_login": True
    }
    
    sync_response = requests.post(
        "http://localhost:5001/api/bulk-users/sync",
        json=sync_data,
        timeout=30
    )
    
    if sync_response.status_code == 200:
        sync_result = sync_response.json()
        print(f"✅ Sync completed: {sync_result}")
    else:
        print(f"❌ Sync failed: {sync_response.status_code}")
        print(sync_response.text)
        
else:
    print(f"❌ User creation failed: {response.status_code}")
    print(response.text)