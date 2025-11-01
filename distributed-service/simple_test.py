#!/usr/bin/env python3
"""
分散サービスの簡単なテストスクリプト
"""

import os
import requests
import time

def test_service_health():
    """サービスのヘルスチェック"""
    service_url = "http://localhost:5002"
    
    print("分散サービスのヘルスチェックを実行します...")
    
    try:
        # ヘルスチェックエンドポイントをテスト
        response = requests.get(f"{service_url}/health", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ ヘルスチェック成功: {data}")
            return True
        else:
            print(f"✗ ヘルスチェック失敗: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"✗ 接続エラー: {e}")
        return False

def test_database_init():
    """データベース初期化のテスト"""
    service_url = "http://localhost:5002"
    
    print("データベース初期化をテストします...")
    
    try:
        # データベース初期化エンドポイントをテスト
        response = requests.post(f"{service_url}/init-db", timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ データベース初期化成功: {data}")
            return True
        else:
            print(f"✗ データベース初期化失敗: {response.status_code}")
            print(f"レスポンス: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"✗ 接続エラー: {e}")
        return False

def main():
    """メイン関数"""
    print("=== 分散サービス 簡単テスト ===")
    
    # サービスが起動するまで少し待つ
    print("サービスの起動を待っています...")
    time.sleep(10)
    
    # ヘルスチェック
    if not test_service_health():
        print("ヘルスチェックに失敗しました")
        return
    
    # データベース初期化テスト
    if not test_database_init():
        print("データベース初期化テストに失敗しました")
        return
    
    print("=== 全てのテストが成功しました ===")

if __name__ == "__main__":
    main()