"""AjaxScenario のユニットテスト

分散トレーシングデモページでの正常系AJAX呼び出しと、
パフォーマンスデモページでの異常系AJAX呼び出しの
各操作シーケンスを、モックされたWebDriverで検証する。
"""

from unittest.mock import MagicMock, patch

import pytest
from selenium.common.exceptions import TimeoutException, WebDriverException

from models import RunnerConfig, TestStatus
from scenarios.ajax import AjaxScenario


@pytest.fixture(autouse=True)
def mock_sleep():
    """全テストでtime.sleepをモック化して高速実行する"""
    with patch("scenarios.base.time.sleep"):
        yield


@pytest.fixture
def mock_driver():
    """モックされたWebDriverを返す"""
    driver = MagicMock()
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
    """AjaxScenarioインスタンスを返す"""
    return AjaxScenario(driver=mock_driver, config=config)


class TestAjaxScenarioInit:
    """AjaxScenario の初期化テスト"""

    def test_name(self, scenario):
        assert scenario.name == "ajax"

    def test_description(self, scenario):
        assert scenario.description == "AJAXリクエスト発生操作によるAjaxRequestイベント生成"

    def test_registered_in_scenario_registry(self):
        """シナリオがレジストリに登録されている"""
        from scenario_engine import SCENARIO_REGISTRY

        assert "ajax" in SCENARIO_REGISTRY
        assert SCENARIO_REGISTRY["ajax"] is AjaxScenario


class TestAjaxScenarioExecute:
    """AjaxScenario.execute のテスト"""

    def test_full_success_returns_completed(self, scenario, mock_driver):
        """全操作成功時にCOMPLETEDステータスを返す"""
        mock_element = MagicMock()

        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.return_value = mock_element
            result = scenario.execute()

        assert result.status == TestStatus.COMPLETED
        assert result.name == "ajax"

    def test_expected_events_count_on_full_success(self, scenario, mock_driver):
        """全操作成功時にexpected_eventsがAJAXリクエスト数を反映する"""
        mock_element = MagicMock()

        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.return_value = mock_element
            result = scenario.execute()

        # 正常系2つ（callNPlusOne, callSlowQuery）+ 異常系1つ（triggerNetworkError）= 3
        assert result.expected_events == {"AjaxRequest": 3}

    def test_distributed_page_navigation_failure_continues(self, scenario, mock_driver):
        """分散トレーシングページ遷移失敗時に異常系テストに進む"""
        mock_element = MagicMock()
        call_count = [0]

        def get_side_effect(url):
            call_count[0] += 1
            if call_count[0] == 1:
                # /distributed/ ページ遷移失敗
                raise TimeoutException("Page load timed out")
            # /performance/js-errors は成功

        mock_driver.get.side_effect = get_side_effect

        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.return_value = mock_element
            result = scenario.execute()

        # 異常系のAJAXリクエストだけ成功 → COMPLETED
        assert result.status == TestStatus.COMPLETED
        assert result.expected_events == {"AjaxRequest": 1}

    def test_all_navigation_failures_returns_failed(self, scenario, mock_driver):
        """全ページ遷移失敗時にFAILEDを返す"""
        mock_driver.get.side_effect = TimeoutException("Page load timed out")

        result = scenario.execute()

        assert result.status == TestStatus.FAILED
        assert result.expected_events == {"AjaxRequest": 0}
        assert result.error_message is not None

    def test_steps_recorded(self, scenario, mock_driver):
        """各操作ステップがstepsに記録される"""
        mock_element = MagicMock()

        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.return_value = mock_element
            result = scenario.execute()

        # 期待: navigate(/distributed/), click(NPlus), click(SlowQuery),
        #        navigate(/performance/js-errors), click(NetworkError)
        assert len(result.steps) == 5
        # ナビゲーションステップが2つ
        nav_steps = [s for s in result.steps if s.action == "navigate"]
        assert len(nav_steps) == 2
        # クリックステップが3つ
        click_steps = [s for s in result.steps if s.action == "click"]
        assert len(click_steps) == 3


class TestAjaxWaitTimes:
    """AJAXリクエスト後の待機時間テスト"""

    def test_click_waits_at_least_3_seconds(self, scenario, mock_driver):
        """AJAXトリガーボタンクリック後に3秒以上待機する"""
        mock_element = MagicMock()

        with patch("scenarios.base.WebDriverWait") as MockWait, \
             patch("scenarios.base.time.sleep") as mock_sleep:
            MockWait.return_value.until.return_value = mock_element
            scenario.execute()

        # click_element(wait_after=3.0) の呼び出しで3秒以上の待機がある
        sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
        three_second_waits = [t for t in sleep_calls if t >= 3.0]
        # 少なくとも3回（各AJAXボタンクリック後）の3秒待機がある
        assert len(three_second_waits) >= 3


class TestAjaxMetadata:
    """AJAXリクエストのメタデータ記録テスト"""

    def test_success_ajax_metadata(self, scenario, mock_driver):
        """正常系AJAXのメタデータが正しく記録される"""
        mock_element = MagicMock()

        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.return_value = mock_element
            result = scenario.execute()

        # 正常系クリックステップのメタデータを確認
        click_steps = [s for s in result.steps if s.action == "click"]
        success_clicks = [s for s in click_steps if s.metadata.get("ajax_type") == "success_200"]
        assert len(success_clicks) == 2
        for step in success_clicks:
            assert step.metadata["page"] == "/distributed/"

    def test_error_ajax_metadata(self, scenario, mock_driver):
        """異常系AJAXのメタデータが正しく記録される"""
        mock_element = MagicMock()

        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.return_value = mock_element
            result = scenario.execute()

        # 異常系クリックステップのメタデータを確認
        click_steps = [s for s in result.steps if s.action == "click"]
        error_clicks = [s for s in click_steps if s.metadata.get("ajax_type") == "error_500"]
        assert len(error_clicks) == 1
        assert error_clicks[0].metadata["page"] == "/performance/js-errors"


class TestAjaxButtonClicks:
    """個別ボタンクリックのテスト"""

    def test_n_plus_one_button_clicked(self, scenario, mock_driver):
        """N+1クエリ実行ボタンがクリックされる"""
        mock_element = MagicMock()

        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.return_value = mock_element
            result = scenario.execute()

        click_steps = [s for s in result.steps if s.action == "click"]
        n_plus_one = [s for s in click_steps if "callNPlusOne" in s.target]
        assert len(n_plus_one) == 1
        assert n_plus_one[0].success is True

    def test_slow_query_button_clicked(self, scenario, mock_driver):
        """スロークエリ実行ボタンがクリックされる"""
        mock_element = MagicMock()

        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.return_value = mock_element
            result = scenario.execute()

        click_steps = [s for s in result.steps if s.action == "click"]
        slow_query = [s for s in click_steps if "callSlowQuery" in s.target]
        assert len(slow_query) == 1
        assert slow_query[0].success is True

    def test_network_error_button_clicked(self, scenario, mock_driver):
        """ネットワークエラーボタンがクリックされる"""
        mock_element = MagicMock()

        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.return_value = mock_element
            result = scenario.execute()

        click_steps = [s for s in result.steps if s.action == "click"]
        network_error = [s for s in click_steps if "triggerNetworkError" in s.target]
        assert len(network_error) == 1
        assert network_error[0].success is True

    def test_button_click_failure_decrements_count(self, scenario, mock_driver):
        """ボタンクリック失敗時にAjaxRequest数が減少する"""
        mock_element = MagicMock()
        click_count = [0]

        def wait_until_side_effect(*args, **kwargs):
            click_count[0] += 1
            if click_count[0] == 2:
                # 2番目のボタン（callSlowQuery）のクリック失敗
                raise TimeoutException("Element not clickable")
            return mock_element

        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.side_effect = wait_until_side_effect
            result = scenario.execute()

        # 1つ失敗したので2つ成功
        assert result.expected_events == {"AjaxRequest": 2}
        assert result.status == TestStatus.COMPLETED


class TestPartialFailures:
    """部分的な失敗シナリオのテスト"""

    def test_only_distributed_page_succeeds(self, scenario, mock_driver):
        """分散トレーシングページのみ成功、JS errorsページ失敗"""
        mock_element = MagicMock()
        call_count = [0]

        def get_side_effect(url):
            call_count[0] += 1
            if "js-errors" in url:
                raise WebDriverException("Connection failed")

        mock_driver.get.side_effect = get_side_effect

        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.return_value = mock_element
            result = scenario.execute()

        assert result.status == TestStatus.COMPLETED
        assert result.expected_events == {"AjaxRequest": 2}

    def test_only_error_page_succeeds(self, scenario, mock_driver):
        """JS errorsページのみ成功、分散トレーシングページ失敗"""
        mock_element = MagicMock()
        call_count = [0]

        def get_side_effect(url):
            call_count[0] += 1
            if "distributed" in url:
                raise WebDriverException("Connection failed")

        mock_driver.get.side_effect = get_side_effect

        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.return_value = mock_element
            result = scenario.execute()

        assert result.status == TestStatus.COMPLETED
        assert result.expected_events == {"AjaxRequest": 1}
