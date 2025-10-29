#!/usr/bin/env python3
import requests
import json

# 小さなテストでユーザー作成
create_data = {
    "count": 1,
    "config": {
        "username_pattern": "debug_api_{id}@example.com",
        "password": "TestPass123!",
        "email_domain": "example.com",
        "batch_size": 1,
        "max_users_per_batch": 1,
        "user_role": "user",
        "custom_attributes": {}
    }
}

print("=== API経由でのユーザー作成デバッグ ===")
print(f"送信データ: {json.dumps(create_data, indent=2)}")

try:
    response = requests.post(
        "http://localhost:5001/api/bulk-users/create",
        json=create_data,
        timeout=30
    )
    
    print(f"レスポンスステータス: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"作成結果: {json.dumps(result, indent=2, ensure_ascii=False)}")
        
        if result.get("created_users"):
            user_info = result["created_users"][0]
            user_id = user_info["user_id"]
            
            # 作成されたユーザーのパスワードを確認
            print(f"\n作成されたユーザー（ID: {user_id}）のパスワード確認...")
            
        else:
            print("ユーザーが作成されませんでした")
    else:
        print(f"エラー: {response.text}")
        
except Exception as e:
    print(f"リクエストエラー: {e}")