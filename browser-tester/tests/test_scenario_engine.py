"""ScenarioEngine のユニットテスト

ScenarioEngineのcreate_driver(), run_scenarios(), wait_for_browser_agent()
をモックされたWebDriverとシナリオで検証する。
"""

import time
from datetime import datetime
from unittest.mock import MagicMock, patch, call

import pytest
from selenium.common.exceptions import WebDriverException

from models import RunnerConfig, RunResult, ScenarioResult, TestStatus
from scenarios.base import BaseScenario
from scenario_engine import ScenarioEngine, SCENARIO_REGISTRY, register_scenario


# テスト用の具象シナリオクラス
class SuccessScenario(BaseScenario):
    name = "success_scenario"
    description = "常に成功するテスト用シナリオ"

    def execute(self) -> ScenarioResult:
        return ScenarioResult(
            name=self.name,
            status=TestStatus.COMPLETED,
            steps=[],
            expected_events={"PageView": 3},
        )


class FailureScenario(BaseScenario):
    name = "failure_scenario"
    description = "常に失敗するテスト用シナリオ"

    def execute(self) -> ScenarioResult:
        return ScenarioResult(
            name=self.name,
            status=TestStatus.FAILED,
            steps=[],
            error_message="Simulated failure",
        )


class ExceptionScenario(BaseScenario):
    name = "exception_scenario"
    description = "例外を発生させるテスト用シナリオ"

    def execute(self) -> ScenarioResult:
        raise RuntimeError("Unexpected scenario error")


class WebDriverExceptionScenario(BaseScenario):
    """WebDriverExceptionを発生させるテスト用シナリオ"""
    name = "webdriver_exception_scenario"
    description = "WebDriverExceptionを発生させるテスト用シナリオ"

    def execute(self) -> ScenarioResult:
        raise WebDriverException("Session not created")


# カウンター付きシナリオ（N回目で成功する）
_attempt_counter = {"count": 0}


class SucceedOnSecondAttemptScenario(BaseScenario):
    """2回目の実行で成功するシナリオ"""
    name = "succeed_on_second_attempt"
    description = "2回目で成功するテスト用シナリオ"

    def execute(self) -> ScenarioResult:
        _attempt_counter["count"] += 1
        if _attempt_counter["count"] >= 2:
            return ScenarioResult(
                name=self.name,
                status=TestStatus.COMPLETED,
                steps=[],
            )
        return ScenarioResult(
            name=self.name,
            status=TestStatus.FAILED,
            error_message="Not yet",
        )


@pytest.fixture
def config():
    """デフォルトのRunnerConfigを返す"""
    return RunnerConfig(
        target_app_url="http://localhost:5000",
        page_wait_seconds=3.0,
        browser_width=1920,
        browser_height=1080,
        retry_count=1,
    )


@pytest.fixture
def engine(config):
    """ScenarioEngineインスタンスを返す"""
    return ScenarioEngine(config=config)


@pytest.fixture(autouse=True)
def setup_registry():
    """テスト前にレジストリをセットアップし、テスト後にクリアする"""
    original_registry = SCENARIO_REGISTRY.copy()
    SCENARIO_REGISTRY.clear()
    SCENARIO_REGISTRY["success_scenario"] = SuccessScenario
    SCENARIO_REGISTRY["failure_scenario"] = FailureScenario
    SCENARIO_REGISTRY["exception_scenario"] = ExceptionScenario
    SCENARIO_REGISTRY["webdriver_exception_scenario"] = WebDriverExceptionScenario
    SCENARIO_REGISTRY["succeed_on_second_attempt"] = SucceedOnSecondAttemptScenario
    yield
    SCENARIO_REGISTRY.clear()
    SCENARIO_REGISTRY.update(original_registry)


class TestCreateDriver:
    """create_driver メソッドのテスト"""

    @patch("scenario_engine.webdriver.Chrome")
    def test_creates_chrome_driver(self, mock_chrome, engine):
        mock_driver = MagicMock()
        mock_chrome.return_value = mock_driver

        driver = engine.create_driver()

        assert driver is mock_driver
        mock_chrome.assert_called_once()

    @patch("scenario_engine.webdriver.Chrome")
    def test_headless_option_set(self, mock_chrome, engine):
        engine.create_driver()

        # ChromeOptionsを確認
        call_kwargs = mock_chrome.call_args
        options = call_kwargs.kwargs.get("options") or call_kwargs[1].get("options")
        args = options.arguments

        assert "--headless" in args

    @patch("scenario_engine.webdriver.Chrome")
    def test_no_sandbox_option_set(self, mock_chrome, engine):
        engine.create_driver()

        call_kwargs = mock_chrome.call_args
        options = call_kwargs.kwargs.get("options") or call_kwargs[1].get("options")
        args = options.arguments

        assert "--no-sandbox" in args

    @patch("scenario_engine.webdriver.Chrome")
    def test_disable_dev_shm_usage_option_set(self, mock_chrome, engine):
        engine.create_driver()

        call_kwargs = mock_chrome.call_args
        options = call_kwargs.kwargs.get("options") or call_kwargs[1].get("options")
        args = options.arguments

        assert "--disable-dev-shm-usage" in args

    @patch("scenario_engine.webdriver.Chrome")
    def test_window_size_from_config(self, mock_chrome, engine):
        engine.config.browser_width = 1280
        engine.config.browser_height = 720

        engine.create_driver()

        call_kwargs = mock_chrome.call_args
        options = call_kwargs.kwargs.get("options") or call_kwargs[1].get("options")
        args = options.arguments

        assert "--window-size=1280,720" in args

    @patch("scenario_engine.webdriver.Chrome")
    def test_disable_web_security_option_set(self, mock_chrome, engine):
        engine.create_driver()

        call_kwargs = mock_chrome.call_args
        options = call_kwargs.kwargs.get("options") or call_kwargs[1].get("options")
        args = options.arguments

        assert "--disable-web-security" in args


class TestRunScenarios:
    """run_scenarios メソッドのテスト"""

    @patch("scenario_engine.ScenarioEngine.create_driver")
    def test_returns_run_result(self, mock_create_driver, engine):
        mock_driver = MagicMock()
        mock_create_driver.return_value = mock_driver

        result = engine.run_scenarios(["success_scenario"])

        assert isinstance(result, RunResult)

    @patch("scenario_engine.ScenarioEngine.create_driver")
    def test_sets_running_then_completed_status(self, mock_create_driver, engine):
        mock_driver = MagicMock()
        mock_create_driver.return_value = mock_driver

        result = engine.run_scenarios(["success_scenario"])

        assert result.status == TestStatus.COMPLETED

    @patch("scenario_engine.ScenarioEngine.create_driver")
    def test_sets_started_at_timestamp(self, mock_create_driver, engine):
        mock_driver = MagicMock()
        mock_create_driver.return_value = mock_driver

        result = engine.run_scenarios(["success_scenario"])

        assert result.started_at is not None
        assert isinstance(result.started_at, datetime)

    @patch("scenario_engine.ScenarioEngine.create_driver")
    def test_sets_completed_at_timestamp(self, mock_create_driver, engine):
        mock_driver = MagicMock()
        mock_create_driver.return_value = mock_driver

        result = engine.run_scenarios(["success_scenario"])

        assert result.completed_at is not None
        assert isinstance(result.completed_at, datetime)
        assert result.completed_at >= result.started_at

    @patch("scenario_engine.ScenarioEngine.create_driver")
    def test_executes_all_scenarios_in_order(self, mock_create_driver, engine):
        mock_driver = MagicMock()
        mock_create_driver.return_value = mock_driver

        result = engine.run_scenarios(["success_scenario", "failure_scenario"])

        assert len(result.scenarios) == 2
        assert result.scenarios[0].name == "success_scenario"
        assert result.scenarios[1].name == "failure_scenario"

    @patch("scenario_engine.ScenarioEngine.create_driver")
    def test_status_failed_when_any_scenario_fails(self, mock_create_driver, engine):
        mock_driver = MagicMock()
        mock_create_driver.return_value = mock_driver

        result = engine.run_scenarios(["success_scenario", "failure_scenario"])

        assert result.status == TestStatus.FAILED

    @patch("scenario_engine.ScenarioEngine.create_driver")
    def test_status_completed_when_all_pass(self, mock_create_driver, engine):
        mock_driver = MagicMock()
        mock_create_driver.return_value = mock_driver

        result = engine.run_scenarios(["success_scenario"])

        assert result.status == TestStatus.COMPLETED

    @patch("scenario_engine.ScenarioEngine.create_driver")
    def test_unknown_scenario_marked_as_failed(self, mock_create_driver, engine):
        mock_driver = MagicMock()
        mock_create_driver.return_value = mock_driver

        result = engine.run_scenarios(["nonexistent_scenario"])

        assert len(result.scenarios) == 1
        assert result.scenarios[0].status == TestStatus.FAILED
        assert "not found in registry" in result.scenarios[0].error_message

    @patch("scenario_engine.ScenarioEngine.create_driver")
    def test_exception_in_scenario_handled(self, mock_create_driver, engine):
        mock_driver = MagicMock()
        mock_create_driver.return_value = mock_driver

        result = engine.run_scenarios(["exception_scenario"])

        assert len(result.scenarios) == 1
        assert result.scenarios[0].status == TestStatus.FAILED
        assert "Unexpected scenario error" in result.scenarios[0].error_message

    @patch("scenario_engine.ScenarioEngine.create_driver")
    def test_driver_quit_called_on_success(self, mock_create_driver, engine):
        mock_driver = MagicMock()
        mock_create_driver.return_value = mock_driver

        engine.run_scenarios(["success_scenario"])

        mock_driver.quit.assert_called_once()

    @patch("scenario_engine.ScenarioEngine.create_driver")
    def test_driver_quit_called_on_failure(self, mock_create_driver, engine):
        mock_driver = MagicMock()
        mock_create_driver.return_value = mock_driver

        engine.run_scenarios(["failure_scenario"])

        mock_driver.quit.assert_called_once()

    @patch("scenario_engine.ScenarioEngine.create_driver")
    def test_driver_quit_called_on_exception(self, mock_create_driver, engine):
        mock_driver = MagicMock()
        mock_create_driver.return_value = mock_driver

        engine.run_scenarios(["exception_scenario"])

        mock_driver.quit.assert_called_once()

    @patch("scenario_engine.ScenarioEngine.create_driver")
    def test_driver_set_to_none_after_run(self, mock_create_driver, engine):
        mock_driver = MagicMock()
        mock_create_driver.return_value = mock_driver

        engine.run_scenarios(["success_scenario"])

        assert engine.driver is None

    @patch("scenario_engine.time.sleep")
    @patch("scenario_engine.ScenarioEngine.create_driver")
    def test_wait_between_scenarios(self, mock_create_driver, mock_sleep, engine):
        mock_driver = MagicMock()
        mock_create_driver.return_value = mock_driver

        engine.run_scenarios(["success_scenario", "success_scenario"])

        # Between two scenarios, wait_for_browser_agent(2.0) should be called once
        mock_sleep.assert_called_with(2.0)

    @patch("scenario_engine.time.sleep")
    @patch("scenario_engine.ScenarioEngine.create_driver")
    def test_no_wait_after_last_scenario(self, mock_create_driver, mock_sleep, engine):
        mock_driver = MagicMock()
        mock_create_driver.return_value = mock_driver

        engine.run_scenarios(["success_scenario"])

        # With only one scenario, no inter-scenario wait should occur
        mock_sleep.assert_not_called()

    @patch("scenario_engine.ScenarioEngine.create_driver")
    def test_config_used_stored_in_result(self, mock_create_driver, engine):
        mock_driver = MagicMock()
        mock_create_driver.return_value = mock_driver

        result = engine.run_scenarios(["success_scenario"])

        assert result.config_used["target_app_url"] == "http://localhost:5000"
        assert result.config_used["browser_width"] == 1920
        assert result.config_used["browser_height"] == 1080
        assert result.config_used["page_wait_seconds"] == 3.0
        assert result.config_used["retry_count"] == 1

    @patch("scenario_engine.ScenarioEngine.create_driver")
    def test_empty_scenario_list(self, mock_create_driver, engine):
        mock_driver = MagicMock()
        mock_create_driver.return_value = mock_driver

        result = engine.run_scenarios([])

        assert result.status == TestStatus.COMPLETED
        assert len(result.scenarios) == 0
        mock_driver.quit.assert_called_once()

    @patch("scenario_engine.ScenarioEngine.create_driver")
    def test_create_driver_failure_sets_failed_status(self, mock_create_driver, engine):
        mock_create_driver.side_effect = Exception("Chrome not available")

        result = engine.run_scenarios(["success_scenario"])

        assert result.status == TestStatus.FAILED
        assert result.completed_at is not None


class TestWaitForBrowserAgent:
    """wait_for_browser_agent メソッドのテスト"""

    @patch("scenario_engine.time.sleep")
    def test_sleeps_for_given_seconds(self, mock_sleep, engine):
        engine.wait_for_browser_agent(2.0)
        mock_sleep.assert_called_once_with(2.0)

    @patch("scenario_engine.time.sleep")
    def test_sleeps_for_custom_duration(self, mock_sleep, engine):
        engine.wait_for_browser_agent(5.5)
        mock_sleep.assert_called_once_with(5.5)

    @patch("scenario_engine.time.sleep")
    def test_sleeps_for_zero(self, mock_sleep, engine):
        engine.wait_for_browser_agent(0)
        mock_sleep.assert_called_once_with(0)


class TestRegisterScenario:
    """register_scenario デコレータのテスト"""

    def test_registers_class_in_registry(self):
        # Clean state for this test
        original = SCENARIO_REGISTRY.copy()
        SCENARIO_REGISTRY.clear()

        @register_scenario
        class TestScenarioReg(BaseScenario):
            name = "test_reg"
            description = "Registration test"

            def execute(self) -> ScenarioResult:
                return ScenarioResult(name=self.name, status=TestStatus.COMPLETED)

        assert "test_reg" in SCENARIO_REGISTRY
        assert SCENARIO_REGISTRY["test_reg"] is TestScenarioReg

        # Restore
        SCENARIO_REGISTRY.clear()
        SCENARIO_REGISTRY.update(original)

    def test_returns_the_class_unchanged(self):
        original = SCENARIO_REGISTRY.copy()
        SCENARIO_REGISTRY.clear()

        @register_scenario
        class AnotherScenario(BaseScenario):
            name = "another"
            description = "Another test"

            def execute(self) -> ScenarioResult:
                return ScenarioResult(name=self.name, status=TestStatus.COMPLETED)

        assert AnotherScenario.name == "another"

        SCENARIO_REGISTRY.clear()
        SCENARIO_REGISTRY.update(original)


class TestScenarioDurationTracking:
    """シナリオ実行のduration_seconds計測テスト"""

    @patch("scenario_engine.ScenarioEngine.create_driver")
    def test_scenario_result_has_duration(self, mock_create_driver, engine):
        mock_driver = MagicMock()
        mock_create_driver.return_value = mock_driver

        result = engine.run_scenarios(["success_scenario"])

        assert result.scenarios[0].duration_seconds >= 0


class TestRetryStrategy:
    """リトライ戦略のテスト

    - 常に失敗するシナリオはN+1回実行される
    - 途中で成功した場合はその時点で停止
    - WebDriverException発生時にドライバー再生成
    - リトライ間に5秒の追加待機
    """

    @patch("scenario_engine.time.sleep")
    @patch("scenario_engine.ScenarioEngine.create_driver")
    def test_always_failing_retries_n_plus_1_times(self, mock_create_driver, mock_sleep, config):
        """常に失敗するシナリオはretry_count+1回実行される"""
        config.retry_count = 2
        engine = ScenarioEngine(config=config)
        mock_driver = MagicMock()
        mock_create_driver.return_value = mock_driver

        # FailureScenarioを使って実行カウントを確認
        call_count = {"count": 0}
        original_execute = FailureScenario.execute

        def counting_execute(self_scenario):
            call_count["count"] += 1
            return original_execute(self_scenario)

        with patch.object(FailureScenario, "execute", counting_execute):
            result = engine.run_scenarios(["failure_scenario"])

        # retry_count=2 なので初回1回 + リトライ2回 = 3回
        assert call_count["count"] == 3
        assert result.scenarios[0].status == TestStatus.FAILED
        assert result.scenarios[0].retry_count == 2

    @patch("scenario_engine.time.sleep")
    @patch("scenario_engine.ScenarioEngine.create_driver")
    def test_succeed_on_second_attempt_stops_retrying(self, mock_create_driver, mock_sleep, config):
        """2回目の実行で成功した場合、リトライを停止する"""
        config.retry_count = 3
        engine = ScenarioEngine(config=config)
        mock_driver = MagicMock()
        mock_create_driver.return_value = mock_driver

        # カウンターをリセット
        _attempt_counter["count"] = 0

        result = engine.run_scenarios(["succeed_on_second_attempt"])

        # 2回目で成功する
        assert result.scenarios[0].status == TestStatus.COMPLETED
        assert result.scenarios[0].retry_count == 1  # attempt index = 1 (0-based)
        assert _attempt_counter["count"] == 2

    @patch("scenario_engine.time.sleep")
    @patch("scenario_engine.ScenarioEngine.create_driver")
    def test_webdriver_exception_triggers_driver_recreation(self, mock_create_driver, mock_sleep, config):
        """WebDriverException発生時にドライバーが再生成される"""
        config.retry_count = 1
        engine = ScenarioEngine(config=config)
        mock_driver = MagicMock()
        mock_create_driver.return_value = mock_driver

        result = engine.run_scenarios(["webdriver_exception_scenario"])

        # 初回 + 1回リトライ = create_driver 2回呼ばれる (初回生成 + 再生成)
        # create_driverは run_scenarios の最初に1回、_recreate_driverで1回
        assert mock_create_driver.call_count == 2
        assert result.scenarios[0].status == TestStatus.FAILED

    @patch("scenario_engine.time.sleep")
    @patch("scenario_engine.ScenarioEngine.create_driver")
    def test_5_second_wait_between_retries(self, mock_create_driver, mock_sleep, config):
        """リトライ間に5秒の待機が挿入される"""
        config.retry_count = 2
        engine = ScenarioEngine(config=config)
        mock_driver = MagicMock()
        mock_create_driver.return_value = mock_driver

        engine.run_scenarios(["failure_scenario"])

        # retry_count=2のため2回の5秒待機が発生する
        five_sec_calls = [c for c in mock_sleep.call_args_list if c == call(5)]
        assert len(five_sec_calls) == 2

    @patch("scenario_engine.time.sleep")
    @patch("scenario_engine.ScenarioEngine.create_driver")
    def test_no_retry_when_retry_count_is_zero(self, mock_create_driver, mock_sleep, config):
        """retry_count=0のときリトライしない"""
        config.retry_count = 0
        engine = ScenarioEngine(config=config)
        mock_driver = MagicMock()
        mock_create_driver.return_value = mock_driver

        call_count = {"count": 0}
        original_execute = FailureScenario.execute

        def counting_execute(self_scenario):
            call_count["count"] += 1
            return original_execute(self_scenario)

        with patch.object(FailureScenario, "execute", counting_execute):
            result = engine.run_scenarios(["failure_scenario"])

        # retry_count=0 なので1回のみ実行
        assert call_count["count"] == 1
        assert result.scenarios[0].status == TestStatus.FAILED
        assert result.scenarios[0].retry_count == 0

    @patch("scenario_engine.time.sleep")
    @patch("scenario_engine.ScenarioEngine.create_driver")
    def test_webdriver_exception_with_5s_wait_before_recreation(self, mock_create_driver, mock_sleep, config):
        """WebDriverException時、5秒待機後にドライバー再生成する"""
        config.retry_count = 1
        engine = ScenarioEngine(config=config)
        mock_driver = MagicMock()
        mock_create_driver.return_value = mock_driver

        engine.run_scenarios(["webdriver_exception_scenario"])

        # WebDriverExceptionの場合も5秒待機が入る
        five_sec_calls = [c for c in mock_sleep.call_args_list if c == call(5)]
        assert len(five_sec_calls) >= 1

    @patch("scenario_engine.time.sleep")
    @patch("scenario_engine.ScenarioEngine.create_driver")
    def test_retry_count_in_result_matches_config(self, mock_create_driver, mock_sleep, config):
        """最終結果のretry_countがconfig.retry_countと一致する（全失敗時）"""
        config.retry_count = 3
        engine = ScenarioEngine(config=config)
        mock_driver = MagicMock()
        mock_create_driver.return_value = mock_driver

        result = engine.run_scenarios(["failure_scenario"])

        assert result.scenarios[0].retry_count == 3

    @patch("scenario_engine.time.sleep")
    @patch("scenario_engine.ScenarioEngine.create_driver")
    def test_driver_quit_called_during_recreation(self, mock_create_driver, mock_sleep, config):
        """ドライバー再生成時に古いドライバーのquitが呼ばれる"""
        config.retry_count = 1
        engine = ScenarioEngine(config=config)
        mock_driver = MagicMock()
        mock_create_driver.return_value = mock_driver

        engine.run_scenarios(["webdriver_exception_scenario"])

        # 初回のドライバーに対してquitが呼ばれる
        # run_scenarios のfinallyで1回 + _recreate_driverで1回
        assert mock_driver.quit.call_count >= 1


class TestRecreateDriver:
    """_recreate_driver メソッドのテスト"""

    @patch("scenario_engine.ScenarioEngine.create_driver")
    def test_recreate_creates_new_driver(self, mock_create_driver, engine):
        """_recreate_driverが新しいドライバーを生成する"""
        old_driver = MagicMock()
        engine.driver = old_driver
        new_driver = MagicMock()
        mock_create_driver.return_value = new_driver

        engine._recreate_driver()

        assert engine.driver is new_driver
        old_driver.quit.assert_called_once()
        mock_create_driver.assert_called_once()

    @patch("scenario_engine.ScenarioEngine.create_driver")
    def test_recreate_handles_quit_exception(self, mock_create_driver, engine):
        """古いドライバーのquitで例外が発生しても新しいドライバーが生成される"""
        old_driver = MagicMock()
        old_driver.quit.side_effect = Exception("Already closed")
        engine.driver = old_driver
        new_driver = MagicMock()
        mock_create_driver.return_value = new_driver

        engine._recreate_driver()

        assert engine.driver is new_driver
        mock_create_driver.assert_called_once()

    @patch("scenario_engine.ScenarioEngine.create_driver")
    def test_recreate_when_driver_is_none(self, mock_create_driver, engine):
        """ドライバーがNoneの状態でも_recreate_driverが動作する"""
        engine.driver = None
        new_driver = MagicMock()
        mock_create_driver.return_value = new_driver

        engine._recreate_driver()

        assert engine.driver is new_driver
        mock_create_driver.assert_called_once()
