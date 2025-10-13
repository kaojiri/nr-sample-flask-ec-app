"""
Basic tests for load testing automation setup
"""
import json
from pathlib import Path
import tempfile
import os
import sys

# Add current directory to path to import config
sys.path.insert(0, '.')

from config import Settings, ConfigManager

def test_settings_defaults():
    """Test that settings have reasonable defaults"""
    settings = Settings()
    
    assert settings.target_app_url == "http://app:5000"
    assert settings.log_level == "INFO"
    assert settings.default_concurrent_users == 10
    assert settings.default_duration_minutes == 30
    assert settings.max_concurrent_users == 50

def test_config_manager_initialization():
    """Test config manager creates default configuration"""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = os.path.join(temp_dir, "test_config.json")
        config_manager = ConfigManager(config_file)
        
        # Check that config file was created
        assert Path(config_file).exists()
        
        # Check that default config is loaded
        config = config_manager.get_config()
        assert "load_test" in config
        assert "endpoints" in config
        assert "safety" in config

def test_config_validation():
    """Test configuration validation"""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = os.path.join(temp_dir, "test_config.json")
        config_manager = ConfigManager(config_file)
        
        # Test valid config update
        valid_config = {
            "load_test": {
                "concurrent_users": 5,
                "duration_minutes": 15
            }
        }
        assert config_manager.update_config(valid_config) == True
        
        # Test invalid config (too many users)
        invalid_config = {
            "load_test": {
                "concurrent_users": 100  # Exceeds max_concurrent_users (50)
            }
        }
        assert config_manager.update_config(invalid_config) == False

def test_config_persistence():
    """Test that configuration is persisted to file"""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = os.path.join(temp_dir, "test_config.json")
        
        # Create config manager and update config
        config_manager = ConfigManager(config_file)
        update_config = {
            "load_test": {
                "concurrent_users": 15
            }
        }
        config_manager.update_config(update_config)
        
        # Create new config manager with same file
        config_manager2 = ConfigManager(config_file)
        config = config_manager2.get_load_test_config()
        
        # Check that the update was persisted
        assert config["concurrent_users"] == 15

if __name__ == "__main__":
    # Run basic tests
    test_settings_defaults()
    test_config_manager_initialization()
    test_config_validation()
    test_config_persistence()
    print("All basic tests passed!")