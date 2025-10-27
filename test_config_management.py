#!/usr/bin/env python3
"""
設定管理とテンプレート機能のテスト
"""
import sys
import os
import json
import tempfile
from pathlib import Path

# アプリケーションのパスを追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'load-tester'))

def test_user_creation_config_validation():
    """UserCreationConfigの検証機能をテスト"""
    print("=== UserCreationConfig検証テスト ===")
    
    try:
        from app.services.bulk_user_creator import UserCreationConfig
        
        # 有効な設定のテスト
        valid_config = UserCreationConfig(
            username_pattern="testuser_{id}@example.com",
            password="TestPass123!",
            email_domain="example.com",
            user_role="user",
            batch_size=100
        )
        
        validation = valid_config.validate()
        print(f"✅ 有効な設定の検証: {validation.is_valid}")
        if validation.warnings:
            print(f"   警告: {validation.warnings}")
        
        # 無効な設定のテスト
        invalid_config = UserCreationConfig(
            username_pattern="",  # 空のパターン
            password="weak",      # 弱いパスワード
            email_domain="invalid",  # 無効なドメイン
            batch_size=0          # 無効なバッチサイズ
        )
        
        validation = invalid_config.validate()
        print(f"❌ 無効な設定の検証: {validation.is_valid}")
        print(f"   エラー: {validation.errors}")
        
        return True
        
    except Exception as e:
        print(f"❌ UserCreationConfig検証テスト失敗: {e}")
        return False


def test_template_manager():
    """テンプレート管理機能をテスト"""
    print("\n=== テンプレート管理テスト ===")
    
    try:
        from app.services.bulk_user_creator import UserCreationTemplateManager
        
        # デフォルトテンプレートの取得
        templates = UserCreationTemplateManager.get_default_templates()
        print(f"✅ デフォルトテンプレート数: {len(templates)}")
        
        # 各テンプレートの検証
        for name, template in templates.items():
            validation = template.validate()
            status = "✅" if validation.is_valid else "❌"
            print(f"   {status} {name}: {validation.is_valid}")
            if validation.errors:
                print(f"      エラー: {validation.errors}")
        
        # 特定テンプレートの取得
        default_template = UserCreationTemplateManager.get_template("default")
        print(f"✅ デフォルトテンプレート取得成功: {default_template.username_pattern}")
        
        # テンプレート情報の取得
        template_info = UserCreationTemplateManager.get_template_info("load_test")
        print(f"✅ テンプレート情報取得: {template_info['name']}")
        
        return True
        
    except Exception as e:
        print(f"❌ テンプレート管理テスト失敗: {e}")
        return False


def test_config_template_manager():
    """設定テンプレート管理クラスをテスト"""
    print("\n=== 設定テンプレート管理テスト ===")
    
    try:
        # 一時ファイルを使用してテスト
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_file = f.name
        
        try:
            from app.services.config_template_manager import ConfigTemplateManager
            from app.services.bulk_user_creator import UserCreationConfig
            
            # テンプレート管理クラスの初期化
            manager = ConfigTemplateManager(temp_file)
            
            # 全テンプレートの取得
            all_templates = manager.get_all_templates()
            print(f"✅ 全テンプレート取得: {len(all_templates)}件")
            
            # カスタムテンプレートの追加
            custom_config = UserCreationConfig(
                username_pattern="custom_{id}@test.com",
                password="CustomPass123!",
                email_domain="test.com",
                user_role="user",
                batch_size=50
            )
            
            result = manager.add_custom_template("custom_test", custom_config)
            print(f"✅ カスタムテンプレート追加: {result.is_valid}")
            
            # テンプレートリストの取得
            template_list = manager.list_templates()
            print(f"✅ テンプレートリスト取得: {len(template_list)}件")
            
            # テンプレートからの設定作成
            config = manager.create_config_from_template("default", {"batch_size": 200})
            print(f"✅ テンプレートから設定作成: batch_size={config.batch_size}")
            
            # エクスポート/インポートテスト
            export_file = temp_file + "_export.json"
            export_success = manager.export_templates(export_file)
            print(f"✅ テンプレートエクスポート: {export_success}")
            
            if export_success:
                # 新しいマネージャーでインポートテスト
                manager2 = ConfigTemplateManager(temp_file + "_import.json")
                import_result = manager2.import_templates(export_file)
                print(f"✅ テンプレートインポート: {len(import_result['imported'])}件")
            
            return True
            
        finally:
            # 一時ファイルのクリーンアップ
            for file_path in [temp_file, temp_file + "_export.json", temp_file + "_import.json"]:
                try:
                    os.unlink(file_path)
                except:
                    pass
        
    except Exception as e:
        print(f"❌ 設定テンプレート管理テスト失敗: {e}")
        return False


def test_load_tester_config():
    """Load Tester設定管理をテスト"""
    print("\n=== Load Tester設定管理テスト ===")
    
    try:
        # Load Testerディレクトリのパスを追加
        load_tester_path = os.path.join(os.path.dirname(__file__), 'load-tester')
        if load_tester_path not in sys.path:
            sys.path.insert(0, load_tester_path)
        
        from config import ConfigManager
        
        # 一時設定ファイルでテスト
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_config = f.name
        
        try:
            manager = ConfigManager(temp_config)
            
            # ユーザー作成テンプレートの取得
            templates = manager.get_user_creation_templates()
            print(f"✅ Load Testerテンプレート取得: {len(templates)}件")
            
            # 特定テンプレートの取得
            default_template = manager.get_user_creation_template("default")
            if default_template:
                print(f"✅ デフォルトテンプレート取得成功")
            
            # カスタムテンプレートの追加
            custom_template = {
                "username_pattern": "loadtest_{id}@test.local",
                "password": "LoadTest123!",
                "email_domain": "test.local",
                "user_role": "user",
                "batch_size": 100,
                "description": "テスト用カスタムテンプレート"
            }
            
            success = manager.add_user_creation_template("test_custom", custom_template)
            print(f"✅ カスタムテンプレート追加: {success}")
            
            # テンプレートリストの取得
            template_names = manager.list_user_creation_templates()
            print(f"✅ テンプレート名リスト: {template_names}")
            
            # 一括ユーザー管理設定の取得
            bulk_config = manager.get_bulk_user_management_config()
            print(f"✅ 一括ユーザー管理設定取得: sync_enabled={bulk_config.get('sync_enabled')}")
            
            return True
            
        finally:
            try:
                os.unlink(temp_config)
            except:
                pass
        
    except Exception as e:
        print(f"❌ Load Tester設定管理テスト失敗: {e}")
        return False


def test_config_validation():
    """設定検証機能の詳細テスト"""
    print("\n=== 設定検証詳細テスト ===")
    
    try:
        from app.services.bulk_user_creator import UserCreationConfig
        
        test_cases = [
            {
                "name": "パスワード長不足",
                "config": {
                    "password": "short",
                    "password_min_length": 10
                },
                "should_fail": True
            },
            {
                "name": "大文字なしパスワード",
                "config": {
                    "password": "lowercase123!",
                    "password_require_uppercase": True
                },
                "should_fail": True
            },
            {
                "name": "数字なしパスワード",
                "config": {
                    "password": "NoNumbers!",
                    "password_require_numbers": True
                },
                "should_fail": True
            },
            {
                "name": "無効なメールドメイン",
                "config": {
                    "email_domain": "invalid-domain"
                },
                "should_fail": True
            },
            {
                "name": "有効な設定",
                "config": {
                    "username_pattern": "test_{id}@example.com",
                    "password": "ValidPass123!",
                    "email_domain": "example.com",
                    "batch_size": 100
                },
                "should_fail": False
            }
        ]
        
        for test_case in test_cases:
            config = UserCreationConfig(**test_case["config"])
            validation = config.validate()
            
            expected_result = not test_case["should_fail"]
            actual_result = validation.is_valid
            
            if expected_result == actual_result:
                print(f"✅ {test_case['name']}: 期待通り")
            else:
                print(f"❌ {test_case['name']}: 期待と異なる結果")
                print(f"   期待: {expected_result}, 実際: {actual_result}")
                if validation.errors:
                    print(f"   エラー: {validation.errors}")
        
        return True
        
    except Exception as e:
        print(f"❌ 設定検証詳細テスト失敗: {e}")
        return False


def main():
    """メインテスト実行"""
    print("設定管理とテンプレート機能のテスト開始")
    print("=" * 50)
    
    tests = [
        test_user_creation_config_validation,
        test_template_manager,
        test_config_template_manager,
        test_load_tester_config,
        test_config_validation
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
    print(f"テスト結果: {passed}/{total} 成功")
    
    if passed == total:
        print("✅ すべてのテストが成功しました！")
        return True
    else:
        print("❌ 一部のテストが失敗しました")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)