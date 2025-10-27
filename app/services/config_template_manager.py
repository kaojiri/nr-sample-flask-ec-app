"""
設定テンプレート管理サービス
ユーザー作成設定のテンプレート機能を提供
"""
from typing import Dict, List, Any, Optional
import json
from pathlib import Path
from dataclasses import asdict
from .bulk_user_creator import UserCreationConfig, ValidationResult, UserCreationTemplateManager


class ConfigTemplateManager:
    """設定テンプレートの管理クラス"""
    
    def __init__(self, template_file_path: str = "data/user_creation_templates.json"):
        self.template_file = Path(template_file_path)
        self.template_file.parent.mkdir(exist_ok=True)
        self._load_templates()
    
    def _load_templates(self):
        """テンプレートファイルから設定を読み込み"""
        if self.template_file.exists():
            try:
                with open(self.template_file, 'r', encoding='utf-8') as f:
                    self.custom_templates = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"テンプレートファイル読み込みエラー: {e}")
                self.custom_templates = {}
        else:
            self.custom_templates = {}
    
    def save_templates(self):
        """テンプレートをファイルに保存"""
        try:
            with open(self.template_file, 'w', encoding='utf-8') as f:
                json.dump(self.custom_templates, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"テンプレートファイル保存エラー: {e}")
    
    def get_all_templates(self) -> Dict[str, UserCreationConfig]:
        """すべてのテンプレート（デフォルト + カスタム）を取得"""
        # デフォルトテンプレートを取得
        templates = UserCreationTemplateManager.get_default_templates()
        
        # カスタムテンプレートを追加
        for name, config_dict in self.custom_templates.items():
            try:
                templates[name] = UserCreationConfig.from_dict(config_dict)
            except Exception as e:
                print(f"カスタムテンプレート '{name}' の読み込みに失敗: {e}")
        
        return templates
    
    def get_template(self, template_name: str) -> Optional[UserCreationConfig]:
        """指定されたテンプレートを取得"""
        templates = self.get_all_templates()
        return templates.get(template_name)
    
    def add_custom_template(self, name: str, config: UserCreationConfig) -> ValidationResult:
        """カスタムテンプレートを追加"""
        # 設定の検証
        validation = config.validate()
        if not validation.is_valid:
            return validation
        
        # カスタムテンプレートとして保存
        self.custom_templates[name] = config.to_dict()
        self.save_templates()
        
        return ValidationResult(is_valid=True)
    
    def remove_custom_template(self, name: str) -> bool:
        """カスタムテンプレートを削除"""
        if name in self.custom_templates:
            del self.custom_templates[name]
            self.save_templates()
            return True
        return False
    
    def list_templates(self) -> Dict[str, Dict[str, Any]]:
        """利用可能なテンプレートのリストと詳細情報を取得"""
        templates = self.get_all_templates()
        result = {}
        
        for name, config in templates.items():
            validation = config.validate()
            result[name] = {
                "name": name,
                "is_default": name in UserCreationTemplateManager.get_default_templates(),
                "is_custom": name in self.custom_templates,
                "config": config.to_dict(),
                "validation": {
                    "is_valid": validation.is_valid,
                    "errors": validation.errors,
                    "warnings": validation.warnings
                },
                "description": self._get_template_description(name)
            }
        
        return result
    
    def _get_template_description(self, template_name: str) -> str:
        """テンプレートの説明を取得"""
        # デフォルトテンプレートの説明
        default_descriptions = {
            "default": "標準的なテストユーザー作成用の基本設定",
            "admin": "管理者権限を持つテストユーザー作成用設定（強化されたパスワードポリシー）",
            "load_test": "負荷テスト用の大量ユーザー作成に最適化された設定",
            "performance_test": "パフォーマンステスト用の超大量ユーザー作成設定",
            "security_test": "セキュリティテスト用の厳格なパスワードポリシー設定"
        }
        
        if template_name in default_descriptions:
            return default_descriptions[template_name]
        
        # カスタムテンプレートの説明
        if template_name in self.custom_templates:
            return self.custom_templates[template_name].get("description", "カスタムテンプレート")
        
        return "説明なし"
    
    def validate_template(self, template_name: str) -> ValidationResult:
        """指定されたテンプレートを検証"""
        template = self.get_template(template_name)
        if not template:
            return ValidationResult(
                is_valid=False,
                errors=[f"テンプレート '{template_name}' が見つかりません"]
            )
        
        return template.validate()
    
    def create_config_from_template(self, template_name: str, overrides: Optional[Dict[str, Any]] = None) -> UserCreationConfig:
        """テンプレートから設定を作成（オーバーライド可能）"""
        template = self.get_template(template_name)
        if not template:
            raise ValueError(f"テンプレート '{template_name}' が見つかりません")
        
        if overrides:
            # テンプレートの設定を辞書に変換
            config_dict = template.to_dict()
            # オーバーライドを適用
            config_dict.update(overrides)
            # 新しい設定オブジェクトを作成
            return UserCreationConfig.from_dict(config_dict)
        
        return template
    
    def export_templates(self, file_path: str) -> bool:
        """テンプレートをファイルにエクスポート"""
        try:
            templates_data = {}
            for name, config in self.get_all_templates().items():
                templates_data[name] = {
                    "config": config.to_dict(),
                    "is_default": name in UserCreationTemplateManager.get_default_templates(),
                    "description": self._get_template_description(name)
                }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(templates_data, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            print(f"テンプレートエクスポートエラー: {e}")
            return False
    
    def import_templates(self, file_path: str, overwrite_existing: bool = False) -> Dict[str, Any]:
        """テンプレートをファイルからインポート"""
        result = {
            "imported": [],
            "skipped": [],
            "errors": []
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                templates_data = json.load(f)
            
            for name, template_info in templates_data.items():
                try:
                    # デフォルトテンプレートはスキップ
                    if template_info.get("is_default", False) and not overwrite_existing:
                        result["skipped"].append(f"デフォルトテンプレート '{name}' をスキップ")
                        continue
                    
                    # 既存のカスタムテンプレートの処理
                    if name in self.custom_templates and not overwrite_existing:
                        result["skipped"].append(f"既存のテンプレート '{name}' をスキップ")
                        continue
                    
                    # 設定を作成して検証
                    config = UserCreationConfig.from_dict(template_info["config"])
                    validation = config.validate()
                    
                    if validation.is_valid:
                        self.custom_templates[name] = config.to_dict()
                        result["imported"].append(name)
                    else:
                        result["errors"].append(f"テンプレート '{name}' の検証に失敗: {validation.errors}")
                
                except Exception as e:
                    result["errors"].append(f"テンプレート '{name}' の処理に失敗: {str(e)}")
            
            if result["imported"]:
                self.save_templates()
        
        except Exception as e:
            result["errors"].append(f"ファイル読み込みエラー: {str(e)}")
        
        return result


# グローバルインスタンス
config_template_manager = ConfigTemplateManager()