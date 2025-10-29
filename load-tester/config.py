"""
Configuration management for Load Testing Automation
"""
from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Dict, Optional, List, Any
import json
import re
from pathlib import Path

class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # Target application settings
    target_app_url: str = Field(
        default="http://web:5000",
        description="URL of the target Flask application"
    )
    
    # Logging settings
    log_level: str = Field(
        default="DEBUG",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)"
    )
    
    # Load testing default settings
    default_concurrent_users: int = Field(
        default=10,
        description="Default number of concurrent users"
    )
    
    default_duration_minutes: int = Field(
        default=30,
        description="Default test duration in minutes"
    )
    
    default_request_interval_min: float = Field(
        default=1.0,
        description="Minimum interval between requests in seconds"
    )
    
    default_request_interval_max: float = Field(
        default=5.0,
        description="Maximum interval between requests in seconds"
    )
    
    max_concurrent_users: int = Field(
        default=50,
        description="Maximum allowed concurrent users"
    )
    
    max_duration_minutes: int = Field(
        default=120,
        description="Maximum allowed test duration in minutes"
    )
    
    # File paths
    config_file_path: str = Field(
        default="data/config.json",
        description="Path to configuration file"
    )
    
    logs_directory: str = Field(
        default="logs",
        description="Directory for log files"
    )
    
    class Config:
        env_file = ".env"
        env_prefix = "LOAD_TESTER_"
        extra = "ignore"  # 追加の環境変数を無視

class ConfigManager:
    """Manages load testing configuration with persistence"""
    
    def __init__(self, config_file: str = "data/config.json"):
        self.config_file = Path(config_file)
        self.config_file.parent.mkdir(exist_ok=True)
        self._load_config()
    
    def _load_config(self):
        """Load configuration from file or create default"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading config file: {e}")
                self.config = self._get_default_config()
        else:
            self.config = self._get_default_config()
            self.save_config()
    
    def _get_default_config(self) -> Dict:
        """Get default configuration"""
        return {
            "target_app_url": settings.target_app_url,
            "load_test": {
                "concurrent_users": settings.default_concurrent_users,
                "duration_minutes": settings.default_duration_minutes,
                "request_interval_min": settings.default_request_interval_min,
                "request_interval_max": settings.default_request_interval_max,
                "max_errors_per_minute": 100,
                "enable_logging": True,
                "enable_user_login": False
            },
            "endpoints": {
                "/performance/slow": {"weight": 1.0, "enabled": True},
                "/performance/n-plus-one": {"weight": 1.0, "enabled": True},
                "/performance/slow-query": {"weight": 1.0, "enabled": True},
                "/performance/js-errors": {"weight": 1.0, "enabled": True},
                "/performance/bad-vitals": {"weight": 1.0, "enabled": True},
                "/performance/error": {"weight": 1.0, "enabled": True, "timeout": 30},
                "/performance/slow-query/full-scan": {"weight": 1.0, "enabled": True, "timeout": 60},
                "/performance/slow-query/complex-join": {"weight": 1.0, "enabled": True, "timeout": 60}
            },
            "test_users": [
                {
                    "user_id": "test_user_1",
                    "username": "testuser1@example.com",
                    "password": "password123",
                    "enabled": True,
                    "description": "Default test user 1"
                },
                {
                    "user_id": "test_user_2",
                    "username": "testuser2@example.com", 
                    "password": "password123",
                    "enabled": True,
                    "description": "Default test user 2"
                },
                {
                    "user_id": "test_user_3",
                    "username": "testuser3@example.com",
                    "password": "password123",
                    "enabled": True,
                    "description": "Default test user 3"
                }
            ],
            "safety": {
                "max_concurrent_users": settings.max_concurrent_users,
                "max_duration_minutes": settings.max_duration_minutes,
                "emergency_stop_enabled": True
            },
            "bulk_user_management": {
                "sync_enabled": True,
                "sync_interval_minutes": 30,
                "auto_login_on_sync": True,
                "max_bulk_users": 1000,
                "cleanup_on_shutdown": True,
                "main_app_url": "http://web:5000",
                "auto_reload_on_import": True,
                "batch_login_enabled": True,
                "preserve_existing_users": False
            },
            "performance_optimization": {
                "bulk_insert_enabled": True,
                "parallel_processing_enabled": True,
                "differential_sync_enabled": True,
                "compression_enabled": True,
                "memory_efficient_mode": True,
                "bulk_insert_chunk_size": 100,
                "max_workers": 4,
                "compression_threshold_bytes": 1024,
                "memory_limit_mb": 512,
                "batch_processing_threshold": 50
            },
            "user_creation_templates": {
                "default": {
                    "username_pattern": "testuser_{id}@example.com",
                    "password": "TestPass123!",
                    "email_domain": "example.com",
                    "user_role": "user",
                    "batch_size": 100,
                    "password_min_length": 8,
                    "password_require_uppercase": True,
                    "password_require_lowercase": True,
                    "password_require_numbers": True,
                    "password_require_special_chars": False,
                    "max_users_per_batch": 1000,
                    "creation_delay_seconds": 0.0,
                    "description": "標準的なテストユーザー作成用の基本設定"
                },
                "admin": {
                    "username_pattern": "admin_{id}@example.com",
                    "password": "AdminPass123!",
                    "email_domain": "example.com",
                    "user_role": "admin",
                    "batch_size": 50,
                    "password_min_length": 12,
                    "password_require_uppercase": True,
                    "password_require_lowercase": True,
                    "password_require_numbers": True,
                    "password_require_special_chars": True,
                    "max_users_per_batch": 100,
                    "creation_delay_seconds": 0.1,
                    "custom_attributes": {"is_admin": True, "permissions": ["read", "write", "admin"]},
                    "description": "管理者権限を持つテストユーザー作成用設定"
                },
                "load_test": {
                    "username_pattern": "loadtest_{id}@loadtest.local",
                    "password": "LoadTest123!",
                    "email_domain": "loadtest.local",
                    "user_role": "user",
                    "batch_size": 200,
                    "password_min_length": 8,
                    "password_require_uppercase": True,
                    "password_require_lowercase": True,
                    "password_require_numbers": True,
                    "password_require_special_chars": False,
                    "max_users_per_batch": 5000,
                    "creation_delay_seconds": 0.0,
                    "custom_attributes": {"test_type": "load", "auto_cleanup": True},
                    "description": "負荷テスト用の大量ユーザー作成に最適化された設定"
                }
            }
        }
    
    def get_config(self) -> Dict:
        """Get current configuration"""
        return self.config.copy()
    
    def update_config(self, new_config: Dict) -> bool:
        """Update configuration with validation"""
        try:
            # Validate the new configuration
            if self._validate_config(new_config):
                self.config.update(new_config)
                self.save_config()
                return True
            return False
        except Exception as e:
            print(f"Error updating config: {e}")
            return False
    
    def save_config(self):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except IOError as e:
            print(f"Error saving config file: {e}")
    
    def _validate_config(self, config: Dict) -> bool:
        """Validate configuration values"""
        if "load_test" in config:
            lt_config = config["load_test"]
            
            # Validate concurrent users
            if "concurrent_users" in lt_config:
                if not (1 <= lt_config["concurrent_users"] <= settings.max_concurrent_users):
                    raise ValueError(f"concurrent_users must be between 1 and {settings.max_concurrent_users}")
            
            # Validate duration
            if "duration_minutes" in lt_config:
                if not (1 <= lt_config["duration_minutes"] <= settings.max_duration_minutes):
                    raise ValueError(f"duration_minutes must be between 1 and {settings.max_duration_minutes}")
            
            # Validate request intervals
            if "request_interval_min" in lt_config and "request_interval_max" in lt_config:
                if lt_config["request_interval_min"] >= lt_config["request_interval_max"]:
                    raise ValueError("request_interval_min must be less than request_interval_max")
        
        return True
    
    def get_load_test_config(self) -> Dict:
        """Get load test specific configuration"""
        return self.config.get("load_test", {})
    
    def get_endpoints_config(self) -> Dict:
        """Get endpoints configuration"""
        return self.config.get("endpoints", {})
    
    def get_safety_config(self) -> Dict:
        """Get safety configuration"""
        return self.config.get("safety", {})
    
    def get_test_users_config(self) -> List[Dict]:
        """Get test users configuration"""
        return self.config.get("test_users", [])
    
    def update_test_users_config(self, test_users: List[Dict]) -> bool:
        """Update test users configuration"""
        try:
            print(f"DEBUG: Updating config with {len(test_users)} users")
            self.config["test_users"] = test_users
            self.save_config()
            print(f"DEBUG: Config saved successfully")
            return True
        except Exception as e:
            print(f"Error updating test users config: {e}")
            return False
    
    def get_bulk_user_management_config(self) -> Dict:
        """Get bulk user management configuration"""
        return self.config.get("bulk_user_management", {})
    
    def update_bulk_user_management_config(self, bulk_config: Dict) -> bool:
        """Update bulk user management configuration"""
        try:
            if "bulk_user_management" not in self.config:
                self.config["bulk_user_management"] = {}
            self.config["bulk_user_management"].update(bulk_config)
            self.save_config()
            return True
        except Exception as e:
            print(f"Error updating bulk user management config: {e}")
            return False
    
    def get_user_creation_templates(self) -> Dict[str, Dict]:
        """Get user creation templates configuration"""
        return self.config.get("user_creation_templates", {})
    
    def get_user_creation_template(self, template_name: str) -> Optional[Dict]:
        """Get specific user creation template"""
        templates = self.get_user_creation_templates()
        return templates.get(template_name)
    
    def add_user_creation_template(self, template_name: str, template_config: Dict) -> bool:
        """Add or update user creation template"""
        try:
            if "user_creation_templates" not in self.config:
                self.config["user_creation_templates"] = {}
            
            # テンプレート設定の検証
            validation_result = self._validate_user_creation_template(template_config)
            if not validation_result["is_valid"]:
                print(f"Template validation failed: {validation_result['errors']}")
                return False
            
            self.config["user_creation_templates"][template_name] = template_config
            self.save_config()
            return True
        except Exception as e:
            print(f"Error adding user creation template: {e}")
            return False
    
    def remove_user_creation_template(self, template_name: str) -> bool:
        """Remove user creation template"""
        try:
            if "user_creation_templates" in self.config and template_name in self.config["user_creation_templates"]:
                del self.config["user_creation_templates"][template_name]
                self.save_config()
                return True
            return False
        except Exception as e:
            print(f"Error removing user creation template: {e}")
            return False
    
    def list_user_creation_templates(self) -> List[str]:
        """List available user creation template names"""
        return list(self.get_user_creation_templates().keys())
    
    def _validate_user_creation_template(self, template_config: Dict) -> Dict[str, Any]:
        """Validate user creation template configuration"""
        errors = []
        warnings = []
        
        # 必須フィールドの検証
        required_fields = ["username_pattern", "password", "email_domain", "user_role"]
        for field in required_fields:
            if field not in template_config:
                errors.append(f"必須フィールドが不足: {field}")
        
        # ユーザー名パターンの検証
        if "username_pattern" in template_config:
            pattern = template_config["username_pattern"]
            if not pattern:
                errors.append("ユーザー名パターンが空です")
            elif "{id}" not in pattern:
                warnings.append("ユーザー名パターンに{id}プレースホルダーがありません")
        
        # メールドメインの検証
        if "email_domain" in template_config:
            domain = template_config["email_domain"]
            if not domain:
                errors.append("メールドメインが空です")
            elif not re.match(r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', domain):
                errors.append("無効なメールドメイン形式です")
        
        # パスワードの検証
        if "password" in template_config:
            password = template_config["password"]
            if len(password) < template_config.get("password_min_length", 8):
                errors.append(f"パスワードが短すぎます（最小: {template_config.get('password_min_length', 8)}文字）")
        
        # バッチサイズの検証
        if "batch_size" in template_config:
            batch_size = template_config["batch_size"]
            if not isinstance(batch_size, int) or batch_size <= 0:
                errors.append("バッチサイズは正の整数である必要があります")
            elif batch_size > 1000:
                warnings.append("バッチサイズが大きすぎます（推奨: 1000以下）")
        
        # 最大ユーザー数の検証
        if "max_users_per_batch" in template_config:
            max_users = template_config["max_users_per_batch"]
            if not isinstance(max_users, int) or max_users <= 0:
                errors.append("最大ユーザー数は正の整数である必要があります")
        
        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }

# Global settings instance
settings = Settings()

# Global config manager instance
config_manager = ConfigManager(settings.config_file_path)