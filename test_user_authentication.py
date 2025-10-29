#!/usr/bin/env python3
import requests

# Load Testerから有効なセッションクッキーを取得
response = requests.get("http://localhost:8080/api/users/sessions")
sessions = response.json()

if sessions.get("active_sessions"):
    # 最初のアクティブセッションを使用
    session = sessions["active_sessions"][0]
    session_cookie = session["session_cookie"]
    username = session["username"]
    
    print(f"Testing authentication with user: {username}")
    print(f"Session cookie: {session_cookie[:50]}...")
    
    # Main Applicationにリクエストを送信
    headers = {
        "Cookie": f"session={session_cookie}",
        "User-Agent": "Test Client"
    }
    
    # ホームページにアクセス
    response = requests.get("http://localhost:5001/", headers=headers)
    print(f"Home page response: {response.status_code}")
    
    # 認証が必要なページにアクセス
    response = requests.get("http://localhost:5001/products", headers=headers)
    print(f"Products page response: {response.status_code}")
    
    if response.status_code == 200:
        print("✅ User authentication successful!")
    else:
        print("❌ User authentication failed")
        print(f"Response: {response.text[:200]}...")
        
else:
    print("No active sessions found")