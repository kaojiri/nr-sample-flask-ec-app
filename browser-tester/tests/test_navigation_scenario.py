"""NavigationScenario のユニットテスト

ページナビゲーションシナリオの動作を検証する。
- 6ページ全てに順次アクセスすること
- 各ページでDOM要素の存在確認とロード時間記録が行われること
- ページ遷移失敗時にFAILEDステータスを返しつつ全ページを試行すること
- expected_eventsにPageView: 6が設定されること
"""

from unittest.mock import MagicMock, patch, call

import pytest
from selenium.common.exceptions import TimeoutException, WebDriverException

from models import RunnerConfig, TestStatus
from scenarios.navigation import NavigationScenario


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
    """NavigationScenarioインスタンスを返す"""
    return NavigationScenario(driver=mock_driver, config=config)


class TestNavigationScenarioMetadata:
    """シナリオのメタデータテスト"""

    def test_name(self, scenario):
        assert scenario.name == "navigation"

    def test_description(self, scenario):
        assert scenario.description == "主要ページへの順次ナビゲーション（PageView生成）"

    def test_pages_count(self, scenario):
        assert len(scenario.PAGES) == 6

    def test_pages_contains_all_required(self, scenario):
        paths = [p[0] for p in scenario.PAGES]
        assert "/" in paths
        assert "/products" in paths
        assert "/products/1" in paths
        assert "/cart" in paths
        assert "/login" in paths
        assert "/register" in paths


class TestNavigationScenarioExecute:
    """execute() メソッドのテスト"""

    def test_visits_all_pages(self, scenario, mock_driver):
        """全6ページにアクセスすること"""
        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.return_value = MagicMock()
            result = scenario.execute()

        assert mock_driver.get.call_count == 6
        expected_urls = [
            call("http://localhost:5000/"),
            call("http://localhost:5000/products"),
            call("http://localhost:5000/products/1"),
            call("http://localhost:5000/cart"),
            call("http://localhost:5000/login"),
            call("http://localhost:5000/register"),
        ]
        mock_driver.get.assert_has_calls(expected_urls, any_order=False)

    def test_returns_completed_when_all_succeed(self, scenario, mock_driver):
        """全ページ成功時にCOMPLETEDステータスを返す"""
        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.return_value = MagicMock()
            result = scenario.execute()

        assert result.status == TestStatus.COMPLETED

    def test_returns_correct_name(self, scenario, mock_driver):
        """結果にシナリオ名が設定される"""
        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.return_value = MagicMock()
            result = scenario.execute()

        assert result.name == "navigation"

    def test_steps_count_equals_pages(self, scenario, mock_driver):
        """ステップ数がページ数と一致する"""
        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.return_value = MagicMock()
            result = scenario.execute()

        assert len(result.steps) == 6

    def test_expected_events_pageview_count(self, scenario, mock_driver):
        """expected_eventsにPageView: 6が設定される"""
        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.return_value = MagicMock()
            result = scenario.execute()

        assert result.expected_events == {"PageView": 6}

    def test_page_names_set_on_steps(self, scenario, mock_driver):
        """各ステップにページ名が設定される"""
        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.return_value = MagicMock()
            result = scenario.execute()

        page_names = [step.page_name for step in result.steps]
        assert "トップページ" in page_names
        assert "商品一覧" in page_names
        assert "商品詳細" in page_names
        assert "カート" in page_names
        assert "ログイン" in page_names
        assert "会員登録" in page_names

    def test_load_time_recorded(self, scenario, mock_driver):
        """各ステップにロード時間が記録される"""
        mock_driver.execute_script.return_value = 350.0
        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.return_value = MagicMock()
            result = scenario.execute()

        for step in result.steps:
            assert step.load_time_ms is not None
            assert step.load_time_ms >= 0

    def test_verified_flag_true_when_element_found(self, scenario, mock_driver):
        """DOM要素が見つかった場合にverified=Trueが設定される"""
        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.return_value = MagicMock()
            result = scenario.execute()

        for step in result.steps:
            assert step.verified is True


class TestNavigationScenarioFailure:
    """失敗時の動作テスト"""

    def test_returns_failed_when_navigation_fails(self, scenario, mock_driver):
        """ページ遷移失敗時にFAILEDステータスを返す"""
        # 最初のページへのナビゲーションが失敗
        mock_driver.get.side_effect = TimeoutException("connection timeout")
        result = scenario.execute()

        assert result.status == TestStatus.FAILED

    def test_continues_after_failure(self, scenario, mock_driver):
        """ページ遷移失敗後も残りのページを試行する"""
        # 最初のページだけ失敗、残りは成功
        mock_driver.get.side_effect = [
            TimeoutException("first page timeout"),
            None, None, None, None, None,
        ]
        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.return_value = MagicMock()
            result = scenario.execute()

        # 全6ページ分のステップが記録される
        assert len(result.steps) == 6
        # 最初は失敗
        assert result.steps[0].success is False
        # ステータスはFAILED（critical failure あり）
        assert result.status == TestStatus.FAILED

    def test_verified_false_when_element_not_found(self, scenario, mock_driver):
        """DOM要素が見つからない場合にverified=Falseが設定される"""
        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.side_effect = TimeoutException("element not found")
            result = scenario.execute()

        for step in result.steps:
            assert step.verified is False

    def test_verified_false_when_navigation_fails(self, scenario, mock_driver):
        """ナビゲーション失敗時にverified=Falseが設定される"""
        mock_driver.get.side_effect = WebDriverException("connection refused")
        result = scenario.execute()

        for step in result.steps:
            assert step.verified is False

    def test_still_sets_expected_events_on_failure(self, scenario, mock_driver):
        """失敗時もexpected_eventsが設定される"""
        mock_driver.get.side_effect = TimeoutException("timeout")
        result = scenario.execute()

        assert result.expected_events == {"PageView": 6}


class TestNavigationScenarioRegistration:
    """シナリオ登録テスト"""

    def test_registered_in_scenario_registry(self):
        """NavigationScenarioがレジストリに登録されていること"""
        from scenario_engine import SCENARIO_REGISTRY
        assert "navigation" in SCENARIO_REGISTRY
        assert SCENARIO_REGISTRY["navigation"] is NavigationScenario
