"""BaseScenario のユニットテスト

タイムアウトハンドリング、duration計測、エラーハンドリング、
最小待機時間の保証をモックされたWebDriverで検証する。
"""

import time
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    WebDriverException,
)

from models import StepResult, ScenarioResult, RunnerConfig, TestStatus
from scenarios.base import BaseScenario


# テスト用の具象クラス（BaseScenarioは抽象クラスのため直接インスタンス化不可）
class ConcreteScenario(BaseScenario):
    name = "test_scenario"
    description = "テスト用シナリオ"

    def execute(self) -> ScenarioResult:
        return ScenarioResult(name=self.name, status=TestStatus.COMPLETED, steps=self.results)


@pytest.fixture
def mock_driver():
    """モックされたWebDriverを返す"""
    driver = MagicMock()
    # デフォルトでは正常なページロード時間を返す
    driver.execute_script.return_value = 500.0
    return driver


@pytest.fixture
def config():
    """デフォルトのRunnerConfigを返す"""
    return RunnerConfig(
        target_app_url="http://localhost:5000",
        page_wait_seconds=3.0,
        page_timeout_seconds=10,
    )


@pytest.fixture
def scenario(mock_driver, config):
    """テスト用シナリオインスタンスを返す"""
    return ConcreteScenario(driver=mock_driver, config=config)


class TestBaseScenarioInit:
    """BaseScenario 初期化テスト"""

    def test_init_stores_driver_and_config(self, mock_driver, config):
        s = ConcreteScenario(driver=mock_driver, config=config)
        assert s.driver is mock_driver
        assert s.config is config
        assert s.results == []

    def test_name_and_description(self, scenario):
        assert scenario.name == "test_scenario"
        assert scenario.description == "テスト用シナリオ"


class TestNavigateTo:
    """navigate_to メソッドのテスト"""

    def test_success_returns_step_result(self, scenario, mock_driver):
        result = scenario.navigate_to("/products")
        assert result.action == "navigate"
        assert result.target == "/products"
        assert result.success is True
        assert result.error_message is None
        mock_driver.get.assert_called_once_with("http://localhost:5000/products")

    def test_duration_ms_is_recorded(self, scenario):
        result = scenario.navigate_to("/")
        # Duration should be positive (at least the wait time of 2+ seconds)
        assert result.duration_ms > 0

    def test_load_time_ms_is_recorded(self, scenario, mock_driver):
        mock_driver.execute_script.return_value = 350.0
        result = scenario.navigate_to("/")
        assert result.load_time_ms == 350.0

    def test_minimum_wait_time_enforced(self, scenario, mock_driver):
        """wait_afterが2秒未満の場合でも最低2秒は待機する"""
        with patch("scenarios.base.time.sleep") as mock_sleep:
            scenario.navigate_to("/", wait_after=0.5)
            # max(0.5, 2.0) = 2.0
            mock_sleep.assert_called_once_with(2.0)

    def test_uses_config_page_wait_seconds_when_none(self, scenario, mock_driver):
        """wait_afterがNoneの場合はconfig.page_wait_secondsを使用"""
        scenario.config.page_wait_seconds = 4.0
        with patch("scenarios.base.time.sleep") as mock_sleep:
            scenario.navigate_to("/")
            # max(4.0, 2.0) = 4.0
            mock_sleep.assert_called_once_with(4.0)

    def test_wait_after_overrides_config(self, scenario, mock_driver):
        """wait_afterが指定された場合はそちらを使用"""
        with patch("scenarios.base.time.sleep") as mock_sleep:
            scenario.navigate_to("/", wait_after=5.0)
            mock_sleep.assert_called_once_with(5.0)

    def test_timeout_returns_failure(self, scenario, mock_driver):
        """TimeoutExceptionが発生した場合はsuccess=Falseを返す"""
        mock_driver.get.side_effect = TimeoutException("Page load timed out")
        result = scenario.navigate_to("/slow-page")
        assert result.success is False
        assert result.action == "navigate"
        assert result.target == "/slow-page"
        assert "Timeout" in result.error_message
        assert result.duration_ms > 0

    def test_webdriver_exception_returns_failure(self, scenario, mock_driver):
        """WebDriverExceptionが発生した場合はsuccess=Falseを返す"""
        mock_driver.get.side_effect = WebDriverException("Connection refused")
        result = scenario.navigate_to("/unreachable")
        assert result.success is False
        assert "WebDriver error" in result.error_message

    def test_does_not_raise_on_error(self, scenario, mock_driver):
        """エラー時に例外を上げず、StepResultを返す"""
        mock_driver.get.side_effect = TimeoutException("timeout")
        # Should not raise
        result = scenario.navigate_to("/timeout")
        assert isinstance(result, StepResult)

    def test_load_time_none_when_script_fails(self, scenario, mock_driver):
        """execute_scriptが失敗した場合はload_time_ms=None"""
        mock_driver.execute_script.side_effect = WebDriverException("script error")
        result = scenario.navigate_to("/")
        assert result.load_time_ms is None


class TestClickElement:
    """click_element メソッドのテスト"""

    def test_success_returns_step_result(self, scenario, mock_driver):
        # WebDriverWaitのモック設定
        mock_element = MagicMock()
        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.return_value = mock_element
            result = scenario.click_element("button.submit")

        assert result.action == "click"
        assert result.target == "button.submit"
        assert result.success is True
        assert result.error_message is None
        mock_element.click.assert_called_once()

    def test_duration_ms_is_recorded(self, scenario, mock_driver):
        with patch("scenarios.base.WebDriverWait") as MockWait:
            mock_element = MagicMock()
            MockWait.return_value.until.return_value = mock_element
            result = scenario.click_element("a.link")
        assert result.duration_ms > 0

    def test_minimum_wait_after_enforced(self, scenario, mock_driver):
        """wait_afterが1秒未満の場合でも最低1秒は待機する"""
        with patch("scenarios.base.WebDriverWait") as MockWait, \
             patch("scenarios.base.time.sleep") as mock_sleep:
            mock_element = MagicMock()
            MockWait.return_value.until.return_value = mock_element
            scenario.click_element("button", wait_after=0.3)
            # max(0.3, 1.0) = 1.0
            mock_sleep.assert_called_once_with(1.0)

    def test_custom_wait_after_used_when_above_minimum(self, scenario, mock_driver):
        """wait_afterが1秒以上の場合はそのまま使用"""
        with patch("scenarios.base.WebDriverWait") as MockWait, \
             patch("scenarios.base.time.sleep") as mock_sleep:
            mock_element = MagicMock()
            MockWait.return_value.until.return_value = mock_element
            scenario.click_element("button", wait_after=3.0)
            mock_sleep.assert_called_once_with(3.0)

    def test_timeout_returns_failure(self, scenario, mock_driver):
        """要素が見つからずタイムアウトした場合はsuccess=False"""
        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.side_effect = TimeoutException(
                "Element not clickable"
            )
            result = scenario.click_element("button.missing")

        assert result.success is False
        assert "Timeout" in result.error_message
        assert "button.missing" in result.error_message
        assert result.duration_ms > 0

    def test_webdriver_exception_returns_failure(self, scenario, mock_driver):
        """WebDriverExceptionが発生した場合はsuccess=False"""
        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.side_effect = WebDriverException("stale element")
            result = scenario.click_element("div.stale")

        assert result.success is False
        assert "WebDriver error" in result.error_message

    def test_does_not_raise_on_error(self, scenario, mock_driver):
        """エラー時に例外を上げず、StepResultを返す"""
        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.side_effect = TimeoutException("timeout")
            result = scenario.click_element("button.gone")
        assert isinstance(result, StepResult)


class TestFillForm:
    """fill_form メソッドのテスト"""

    def test_success_returns_step_result(self, scenario, mock_driver):
        mock_element = MagicMock()
        mock_driver.find_element.return_value = mock_element
        result = scenario.fill_form("input[name='email']", "test@example.com")

        assert result.action == "fill"
        assert result.target == "input[name='email']"
        assert result.success is True
        mock_element.clear.assert_called_once()
        mock_element.send_keys.assert_called_once_with("test@example.com")

    def test_duration_ms_is_recorded(self, scenario, mock_driver):
        mock_element = MagicMock()
        mock_driver.find_element.return_value = mock_element
        result = scenario.fill_form("input", "value")
        assert result.duration_ms >= 0

    def test_no_such_element_returns_failure(self, scenario, mock_driver):
        """要素が見つからない場合はsuccess=False"""
        mock_driver.find_element.side_effect = NoSuchElementException("not found")
        result = scenario.fill_form("input.missing", "value")

        assert result.success is False
        assert "Error filling form element" in result.error_message
        assert "input.missing" in result.error_message

    def test_webdriver_exception_returns_failure(self, scenario, mock_driver):
        """WebDriverExceptionが発生した場合はsuccess=False"""
        mock_driver.find_element.side_effect = WebDriverException("driver error")
        result = scenario.fill_form("input", "value")
        assert result.success is False

    def test_does_not_raise_on_error(self, scenario, mock_driver):
        """エラー時に例外を上げない"""
        mock_driver.find_element.side_effect = NoSuchElementException("not found")
        result = scenario.fill_form("input", "value")
        assert isinstance(result, StepResult)


class TestVerifyElementExists:
    """verify_element_exists メソッドのテスト"""

    def test_returns_true_when_element_found(self, scenario, mock_driver):
        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.return_value = MagicMock()
            assert scenario.verify_element_exists("h1.title") is True

    def test_returns_false_on_timeout(self, scenario, mock_driver):
        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.side_effect = TimeoutException("timeout")
            assert scenario.verify_element_exists("div.nonexistent") is False

    def test_custom_timeout_passed(self, scenario, mock_driver):
        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.return_value = MagicMock()
            scenario.verify_element_exists("div", timeout=5)
            MockWait.assert_called_once_with(mock_driver, 5)


class TestGetPageLoadTime:
    """get_page_load_time メソッドのテスト"""

    def test_returns_positive_value(self, scenario, mock_driver):
        mock_driver.execute_script.return_value = 1200.0
        result = scenario.get_page_load_time()
        assert result == 1200.0

    def test_returns_zero_as_valid(self, scenario, mock_driver):
        mock_driver.execute_script.return_value = 0
        result = scenario.get_page_load_time()
        assert result == 0.0

    def test_returns_none_for_negative(self, scenario, mock_driver):
        """Navigation Timing APIが負の値を返した場合はNone"""
        mock_driver.execute_script.return_value = -1
        result = scenario.get_page_load_time()
        assert result is None

    def test_returns_none_when_script_returns_none(self, scenario, mock_driver):
        """execute_scriptがNoneを返した場合はNone"""
        mock_driver.execute_script.return_value = None
        result = scenario.get_page_load_time()
        assert result is None

    def test_returns_none_on_webdriver_exception(self, scenario, mock_driver):
        """WebDriverExceptionが発生した場合はNone"""
        mock_driver.execute_script.side_effect = WebDriverException("script error")
        result = scenario.get_page_load_time()
        assert result is None


class TestDurationMeasurement:
    """duration計測の正確性テスト"""

    def test_navigate_to_duration_includes_wait(self, scenario, mock_driver):
        """navigate_toのdurationには待機時間が含まれる"""
        result = scenario.navigate_to("/", wait_after=2.0)
        # 少なくとも2000ms（2秒の待機）以上のはず
        assert result.duration_ms >= 2000

    def test_click_element_duration_includes_wait(self, scenario, mock_driver):
        """click_elementのdurationには待機時間が含まれる"""
        with patch("scenarios.base.WebDriverWait") as MockWait:
            mock_element = MagicMock()
            MockWait.return_value.until.return_value = mock_element
            result = scenario.click_element("button", wait_after=1.0)
        # 少なくとも1000ms（1秒の待機）以上のはず
        assert result.duration_ms >= 1000


class TestErrorContinuation:
    """エラー発生後にシナリオが継続できることのテスト"""

    def test_navigate_timeout_allows_next_operation(self, scenario, mock_driver):
        """navigate_toのタイムアウト後に次の操作が可能"""
        mock_driver.get.side_effect = [
            TimeoutException("first timeout"),
            None,  # 2回目は成功
        ]
        result1 = scenario.navigate_to("/timeout-page")
        assert result1.success is False

        # 2回目の呼び出しは正常に動作する
        result2 = scenario.navigate_to("/normal-page")
        assert result2.success is True

    def test_click_timeout_allows_next_operation(self, scenario, mock_driver):
        """click_elementのタイムアウト後に次の操作が可能"""
        with patch("scenarios.base.WebDriverWait") as MockWait:
            mock_element = MagicMock()
            # 1回目はタイムアウト、2回目は成功
            MockWait.return_value.until.side_effect = [
                TimeoutException("first timeout"),
                mock_element,
            ]
            result1 = scenario.click_element("button.missing")
            assert result1.success is False

            result2 = scenario.click_element("button.exists")
            assert result2.success is True
