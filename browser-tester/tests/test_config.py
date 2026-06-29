"""config.py のユニットテスト: 環境変数ベースの設定パーサ"""

import os
import pytest
from config import load_config_from_env
from models import RunnerConfig


class TestLoadConfigFromEnv:
    """load_config_from_env関数のテスト"""

    def test_all_defaults_when_no_env_vars(self, monkeypatch):
        """環境変数が未設定の場合、全てデフォルト値が使用される"""
        # 対象の環境変数を全て削除
        for key in ["TARGET_APP_URL", "PAGE_WAIT_SECONDS", "BROWSER_WIDTH",
                    "BROWSER_HEIGHT", "RETRY_COUNT", "LOG_LEVEL",
                    "PAGE_TIMEOUT_SECONDS"]:
            monkeypatch.delenv(key, raising=False)

        config = load_config_from_env()

        assert config.target_app_url == "http://web:5000"
        assert config.page_wait_seconds == 3.0
        assert config.browser_width == 1920
        assert config.browser_height == 1080
        assert config.retry_count == 1
        assert config.page_timeout_seconds == 10
        assert config.log_level == "INFO"

    def test_valid_target_app_url(self, monkeypatch):
        """有効なTARGET_APP_URLが設定された場合"""
        monkeypatch.setenv("TARGET_APP_URL", "http://localhost:8080")
        config = load_config_from_env()
        assert config.target_app_url == "http://localhost:8080"

    def test_empty_target_app_url_uses_default(self, monkeypatch):
        """空文字のTARGET_APP_URLはデフォルトにフォールバック"""
        monkeypatch.setenv("TARGET_APP_URL", "")
        config = load_config_from_env()
        assert config.target_app_url == "http://web:5000"

    def test_whitespace_target_app_url_uses_default(self, monkeypatch):
        """空白文字のみのTARGET_APP_URLはデフォルトにフォールバック"""
        monkeypatch.setenv("TARGET_APP_URL", "   ")
        config = load_config_from_env()
        assert config.target_app_url == "http://web:5000"

    def test_valid_page_wait_seconds(self, monkeypatch):
        """有効なPAGE_WAIT_SECONDSが設定された場合"""
        monkeypatch.setenv("PAGE_WAIT_SECONDS", "5.5")
        config = load_config_from_env()
        assert config.page_wait_seconds == 5.5

    def test_invalid_page_wait_seconds_non_numeric(self, monkeypatch):
        """非数値のPAGE_WAIT_SECONDSはデフォルトにフォールバック"""
        monkeypatch.setenv("PAGE_WAIT_SECONDS", "abc")
        config = load_config_from_env()
        assert config.page_wait_seconds == 3.0

    def test_negative_page_wait_seconds_uses_default(self, monkeypatch):
        """負の値のPAGE_WAIT_SECONDSはデフォルトにフォールバック"""
        monkeypatch.setenv("PAGE_WAIT_SECONDS", "-1.0")
        config = load_config_from_env()
        assert config.page_wait_seconds == 3.0

    def test_zero_page_wait_seconds_uses_default(self, monkeypatch):
        """0のPAGE_WAIT_SECONDSはデフォルトにフォールバック"""
        monkeypatch.setenv("PAGE_WAIT_SECONDS", "0")
        config = load_config_from_env()
        assert config.page_wait_seconds == 3.0

    def test_valid_browser_width(self, monkeypatch):
        """有効なBROWSER_WIDTHが設定された場合"""
        monkeypatch.setenv("BROWSER_WIDTH", "1280")
        config = load_config_from_env()
        assert config.browser_width == 1280

    def test_invalid_browser_width_non_integer(self, monkeypatch):
        """非整数のBROWSER_WIDTHはデフォルトにフォールバック"""
        monkeypatch.setenv("BROWSER_WIDTH", "12.5")
        config = load_config_from_env()
        assert config.browser_width == 1920

    def test_negative_browser_width_uses_default(self, monkeypatch):
        """負の値のBROWSER_WIDTHはデフォルトにフォールバック"""
        monkeypatch.setenv("BROWSER_WIDTH", "-100")
        config = load_config_from_env()
        assert config.browser_width == 1920

    def test_valid_browser_height(self, monkeypatch):
        """有効なBROWSER_HEIGHTが設定された場合"""
        monkeypatch.setenv("BROWSER_HEIGHT", "720")
        config = load_config_from_env()
        assert config.browser_height == 720

    def test_invalid_browser_height_non_numeric(self, monkeypatch):
        """非数値のBROWSER_HEIGHTはデフォルトにフォールバック"""
        monkeypatch.setenv("BROWSER_HEIGHT", "tall")
        config = load_config_from_env()
        assert config.browser_height == 1080

    def test_valid_retry_count(self, monkeypatch):
        """有効なRETRY_COUNTが設定された場合"""
        monkeypatch.setenv("RETRY_COUNT", "3")
        config = load_config_from_env()
        assert config.retry_count == 3

    def test_zero_retry_count_is_valid(self, monkeypatch):
        """RETRY_COUNT=0は有効（リトライなし）"""
        monkeypatch.setenv("RETRY_COUNT", "0")
        config = load_config_from_env()
        assert config.retry_count == 0

    def test_negative_retry_count_uses_default(self, monkeypatch):
        """負のRETRY_COUNTはデフォルトにフォールバック"""
        monkeypatch.setenv("RETRY_COUNT", "-1")
        config = load_config_from_env()
        assert config.retry_count == 1

    def test_valid_log_level(self, monkeypatch):
        """有効なLOG_LEVELが設定された場合"""
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        config = load_config_from_env()
        assert config.log_level == "DEBUG"

    def test_log_level_case_insensitive(self, monkeypatch):
        """LOG_LEVELは大文字小文字を区別しない"""
        monkeypatch.setenv("LOG_LEVEL", "warning")
        config = load_config_from_env()
        assert config.log_level == "WARNING"

    def test_invalid_log_level_uses_default(self, monkeypatch):
        """無効なLOG_LEVELはデフォルトにフォールバック"""
        monkeypatch.setenv("LOG_LEVEL", "VERBOSE")
        config = load_config_from_env()
        assert config.log_level == "INFO"

    def test_empty_log_level_uses_default(self, monkeypatch):
        """空文字のLOG_LEVELはデフォルトにフォールバック"""
        monkeypatch.setenv("LOG_LEVEL", "")
        config = load_config_from_env()
        assert config.log_level == "INFO"

    def test_all_valid_env_vars(self, monkeypatch):
        """全ての環境変数が有効な値で設定された場合"""
        monkeypatch.setenv("TARGET_APP_URL", "http://myapp:3000")
        monkeypatch.setenv("PAGE_WAIT_SECONDS", "2.0")
        monkeypatch.setenv("BROWSER_WIDTH", "1366")
        monkeypatch.setenv("BROWSER_HEIGHT", "768")
        monkeypatch.setenv("RETRY_COUNT", "2")
        monkeypatch.setenv("LOG_LEVEL", "ERROR")

        config = load_config_from_env()

        assert config.target_app_url == "http://myapp:3000"
        assert config.page_wait_seconds == 2.0
        assert config.browser_width == 1366
        assert config.browser_height == 768
        assert config.retry_count == 2
        assert config.log_level == "ERROR"

    def test_returns_runner_config_instance(self, monkeypatch):
        """戻り値がRunnerConfigインスタンスであること"""
        config = load_config_from_env()
        assert isinstance(config, RunnerConfig)

    def test_target_url_with_trailing_spaces_trimmed(self, monkeypatch):
        """TARGET_APP_URLの前後の空白が除去される"""
        monkeypatch.setenv("TARGET_APP_URL", "  http://example.com  ")
        config = load_config_from_env()
        assert config.target_app_url == "http://example.com"

    def test_valid_page_timeout_seconds(self, monkeypatch):
        """有効なPAGE_TIMEOUT_SECONDSが設定された場合"""
        monkeypatch.setenv("PAGE_TIMEOUT_SECONDS", "20")
        config = load_config_from_env()
        assert config.page_timeout_seconds == 20

    def test_invalid_page_timeout_seconds_non_integer(self, monkeypatch):
        """非整数のPAGE_TIMEOUT_SECONDSはデフォルトにフォールバック"""
        monkeypatch.setenv("PAGE_TIMEOUT_SECONDS", "abc")
        config = load_config_from_env()
        assert config.page_timeout_seconds == 10

    def test_negative_page_timeout_seconds_uses_default(self, monkeypatch):
        """負の値のPAGE_TIMEOUT_SECONDSはデフォルトにフォールバック"""
        monkeypatch.setenv("PAGE_TIMEOUT_SECONDS", "-5")
        config = load_config_from_env()
        assert config.page_timeout_seconds == 10

    def test_zero_page_timeout_seconds_uses_default(self, monkeypatch):
        """0のPAGE_TIMEOUT_SECONDSはデフォルトにフォールバック"""
        monkeypatch.setenv("PAGE_TIMEOUT_SECONDS", "0")
        config = load_config_from_env()
        assert config.page_timeout_seconds == 10
