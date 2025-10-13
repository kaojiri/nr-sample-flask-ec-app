"""
Configuration management for Load Testing Automation
"""
from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Dict, Optional
import json
from pathlib import Path

class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # Target application settings
    target_app_url: str = Field(
        default="http://app:5000",
        description="URL of the target Flask application"
    )
    
    # Logging settings
    log_level: str = Field(
        default="INFO",
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
                "enable_logging": True
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
            "safety": {
                "max_concurrent_users": settings.max_concurrent_users,
                "max_duration_minutes": settings.max_duration_minutes,
                "emergency_stop_enabled": True
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

# Global settings instance
settings = Settings()

# Global config manager instance
config_manager = ConfigManager(settings.config_file_path)