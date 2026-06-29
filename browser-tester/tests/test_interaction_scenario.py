"""InteractionScenario のユニットテスト

ログインフォーム操作、商品リンククリック、カート追加ボタンクリックの
各操作シーケンスを、モックされたWebDriverで検証する。
"""

from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from selenium.common.exceptions import TimeoutException, WebDriverException

from models import RunnerConfig, TestStatus
from scenarios.interaction import InteractionScenario


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
    driver.current_url = "http://localhost:5000/products/1"
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
    """InteractionScenarioインスタンスを返す"""
    return InteractionScenario(driver=mock_driver, config=config)


class TestInteractionScenarioInit:
    """InteractionScenario の初期化テスト"""

    def test_name(self, scenario):
        assert scenario.name == "interaction"

    def test_description(self, scenario):
        assert scenario.description == "ユーザー操作（クリック、フォーム入力）によるBrowserInteraction生成"


class TestInteractionScenarioExecute:
    """InteractionScenario.execute のテスト"""

    def test_full_success_returns_completed(self, scenario, mock_driver):
        """全操作成功時にCOMPLETEDステータスを返す"""
        mock_element = MagicMock()
        mock_driver.find_element.return_value = mock_element

        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.return_value = mock_element
            result = scenario.execute()

        assert result.status == TestStatus.COMPLETED
        assert result.name == "interaction"
        assert result.expected_events == {"BrowserInteraction": 4}

    def test_login_failure_returns_failed(self, scenario, mock_driver):
        """ログインページ遷移失敗時にFAILEDステータスを返す"""
        mock_driver.get.side_effect = TimeoutException("Page load timed out")

        result = scenario.execute()

        assert result.status == TestStatus.FAILED
        assert result.name == "interaction"

    def test_login_success_product_failure_returns_completed(self, scenario, mock_driver):
        """ログイン成功、商品操作全失敗でもCOMPLETEDを返す"""
        mock_element = MagicMock()
        mock_driver.find_element.return_value = mock_element

        call_count = [0]

        def wait_until_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 1:
                # submit button click - success
                return mock_element
            # product link click - failure
            raise TimeoutException("Element not found")

        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.side_effect = wait_until_side_effect
            result = scenario.execute()

        # ログインは成功したがインタラクションが失敗 -> COMPLETED
        assert result.status == TestStatus.COMPLETED

    def test_expected_events_set_correctly(self, scenario, mock_driver):
        """expected_eventsが正しく設定される"""
        mock_element = MagicMock()
        mock_driver.find_element.return_value = mock_element

        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.return_value = mock_element
            result = scenario.execute()

        assert result.expected_events == {"BrowserInteraction": 4}

    def test_steps_recorded(self, scenario, mock_driver):
        """各操作ステップがresultsに記録される"""
        mock_element = MagicMock()
        mock_driver.find_element.return_value = mock_element

        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.return_value = mock_element
            result = scenario.execute()

        # 期待するステップ: navigate(/login), fill(username), fill(password),
        # click(submit), navigate(/products), click(product link), click(cart add)
        assert len(result.steps) >= 5  # At minimum: navigate, fill, fill, click, navigate


class TestLoginForm:
    """ログインフォーム操作のテスト"""

    def test_login_navigates_to_login_page(self, scenario, mock_driver):
        """ログインページに遷移する"""
        mock_element = MagicMock()
        mock_driver.find_element.return_value = mock_element

        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.return_value = mock_element
            scenario.execute()

        # 最初のget呼び出しが/loginへの遷移
        calls = mock_driver.get.call_args_list
        assert any("login" in str(call) for call in calls)

    def test_login_fills_username_and_password(self, scenario, mock_driver):
        """ユーザー名とパスワードを入力する"""
        mock_element = MagicMock()
        mock_driver.find_element.return_value = mock_element

        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.return_value = mock_element
            scenario.execute()

        # send_keys呼び出しでusernameとpasswordが入力されている
        send_keys_calls = mock_element.send_keys.call_args_list
        values_sent = [call[0][0] for call in send_keys_calls]
        assert "testuser" in values_sent
        assert "password" in values_sent

    def test_login_clicks_submit(self, scenario, mock_driver):
        """送信ボタンをクリックする"""
        mock_element = MagicMock()
        mock_driver.find_element.return_value = mock_element

        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.return_value = mock_element
            scenario.execute()

        # click()が呼ばれている（submit, product link, cart add）
        assert mock_element.click.called

    def test_login_submit_wait_time(self, scenario, mock_driver):
        """送信ボタンクリック後に2秒以上待機する"""
        mock_element = MagicMock()
        mock_driver.find_element.return_value = mock_element

        with patch("scenarios.base.WebDriverWait") as MockWait, \
             patch("scenarios.base.time.sleep") as mock_sleep:
            MockWait.return_value.until.return_value = mock_element
            scenario.execute()

        # 2.0秒のwait_afterが渡されている呼び出しがある
        sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
        assert any(t >= 2.0 for t in sleep_calls)

    def test_username_fill_failure_stops_login(self, scenario, mock_driver):
        """ユーザー名入力失敗時にログインを中止する"""
        from selenium.common.exceptions import NoSuchElementException

        # navigate succeeds, but find_element fails
        call_count = [0]

        def find_element_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise NoSuchElementException("username not found")
            return MagicMock()

        mock_driver.find_element.side_effect = find_element_side_effect

        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.return_value = MagicMock()
            result = scenario.execute()

        # ログイン失敗 -> FAILEDステータス
        assert result.status == TestStatus.FAILED


class TestProductInteractions:
    """商品ページインタラクションのテスト"""

    def test_navigates_to_products_page(self, scenario, mock_driver):
        """商品一覧ページに遷移する"""
        mock_element = MagicMock()
        mock_driver.find_element.return_value = mock_element

        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.return_value = mock_element
            scenario.execute()

        calls = mock_driver.get.call_args_list
        assert any("products" in str(call) for call in calls)

    def test_product_link_click_wait_time(self, scenario, mock_driver):
        """商品リンククリック後に2秒以上待機する"""
        mock_element = MagicMock()
        mock_driver.find_element.return_value = mock_element

        with patch("scenarios.base.WebDriverWait") as MockWait, \
             patch("scenarios.base.time.sleep") as mock_sleep:
            MockWait.return_value.until.return_value = mock_element
            scenario.execute()

        # 2.0秒以上のsleep呼び出しが複数回ある（submit + product click + cart add）
        sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
        two_second_waits = [t for t in sleep_calls if t >= 2.0]
        assert len(two_second_waits) >= 2  # at least submit and product click

    def test_cart_add_click_after_product(self, scenario, mock_driver):
        """商品リンククリック成功後にカート追加ボタンをクリックする"""
        mock_element = MagicMock()
        mock_driver.find_element.return_value = mock_element

        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.return_value = mock_element
            result = scenario.execute()

        # click()が3回以上呼ばれる（submit, product link, cart add）
        assert mock_element.click.call_count >= 3

    def test_product_click_failure_skips_cart(self, scenario, mock_driver):
        """商品リンククリック失敗時にカート追加をスキップする"""
        mock_element = MagicMock()
        mock_driver.find_element.return_value = mock_element

        call_count = [0]

        def wait_until_side_effect(*args, **kwargs):
            call_count[0] += 1
            # Call sequence:
            # 1: click_element for submit button -> success
            # 2: verify_element_exists after login -> success
            # 3: click_element for product link -> FAIL
            if call_count[0] == 1:
                return mock_element  # submit button
            elif call_count[0] == 2:
                return mock_element  # verify_element_exists after login
            elif call_count[0] == 3:
                raise TimeoutException("Product link not found")
            return mock_element

        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.side_effect = wait_until_side_effect
            result = scenario.execute()

        # 商品リンクが失敗したので、カート追加のステップは記録されない
        cart_steps = [s for s in result.steps
                      if s.action == "click" and "cart" in s.target]
        assert len(cart_steps) == 0

    def test_url_change_verification_after_product_click(self, scenario, mock_driver):
        """商品リンククリック後にURL変更が記録される"""
        mock_element = MagicMock()
        mock_driver.find_element.return_value = mock_element
        mock_driver.current_url = "http://localhost:5000/products/1"

        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.return_value = mock_element
            result = scenario.execute()

        # URL変更を検証するステップがある
        click_steps_with_url = [
            s for s in result.steps
            if s.action == "click" and s.metadata.get("url_after")
        ]
        assert len(click_steps_with_url) > 0


class TestStateVerification:
    """操作後のページ状態変化検証のテスト"""

    def test_login_verifies_url_change(self, scenario, mock_driver):
        """ログイン送信後にURL変更を確認する"""
        mock_element = MagicMock()
        mock_driver.find_element.return_value = mock_element
        # ログイン後にURLが変わったことをシミュレート
        mock_driver.current_url = "http://localhost:5000/"

        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.return_value = mock_element
            result = scenario.execute()

        # submit ステップのmetadataにurl_changedがTrueで記録される
        submit_steps = [
            s for s in result.steps
            if s.action == "click" and "submit" in s.target
        ]
        assert len(submit_steps) == 1
        assert submit_steps[0].metadata.get("url_changed") is True

    def test_product_click_verifies_dom(self, scenario, mock_driver):
        """商品クリック後にDOM要素出現を確認する"""
        mock_element = MagicMock()
        mock_driver.find_element.return_value = mock_element
        mock_driver.current_url = "http://localhost:5000/products/3"

        with patch("scenarios.base.WebDriverWait") as MockWait:
            MockWait.return_value.until.return_value = mock_element
            result = scenario.execute()

        # 商品リンクのクリックステップでverifiedが設定されている
        product_clicks = [
            s for s in result.steps
            if s.action == "click" and "card" in s.target or "product" in s.target
        ]
        # At least one click step should have verified set
        assert any(s.verified for s in product_clicks if s.success)
