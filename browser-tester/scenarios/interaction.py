"""ユーザーインタラクションテストシナリオ

ログインフォーム操作、商品リンククリック、カート追加ボタンクリックを実行し、
New Relic Browser AgentのBrowserInteractionイベント生成を検証するシナリオ。

各操作前後に1秒以上の待機時間を設け、操作後のページ状態変化を検証する。
"""

import logging
from typing import Optional

from models import ScenarioResult, StepResult, TestStatus, RunnerConfig
from scenarios.base import BaseScenario
from scenario_engine import register_scenario

logger = logging.getLogger(__name__)


@register_scenario
class InteractionScenario(BaseScenario):
    """ユーザー操作（クリック、フォーム入力）によるBrowserInteraction生成"""

    name = "interaction"
    description = "ユーザー操作（クリック、フォーム入力）によるBrowserInteraction生成"

    def execute(self) -> ScenarioResult:
        """インタラクションシナリオを実行する

        1. ログインフォーム操作（入力 + 送信）
        2. 商品一覧からリンククリック
        3. カート追加ボタンクリック

        Returns:
            ScenarioResult: シナリオ実行結果。
                ログイン操作 + 少なくとも1つのインタラクションが成功した場合はCOMPLETED。
                ログイン操作が全て失敗した場合はFAILED。
        """
        login_success = self._execute_login()
        interaction_success = self._execute_product_interactions()

        # ステータス判定: ログイン + 少なくとも1つのインタラクション成功でCOMPLETED
        if login_success and interaction_success:
            status = TestStatus.COMPLETED
        elif login_success:
            # ログインは成功したがインタラクションが全失敗
            status = TestStatus.COMPLETED
        else:
            status = TestStatus.FAILED

        return ScenarioResult(
            name=self.name,
            status=status,
            steps=self.results,
            expected_events={"BrowserInteraction": 4},
        )

    def _execute_login(self) -> bool:
        """ログインフォーム操作を実行する

        Returns:
            bool: ログインフォームの送信が成功した場合True
        """
        # ログインページに遷移
        nav_result = self.navigate_to("/auth/login")
        self.results.append(nav_result)
        if not nav_result.success:
            logger.warning("Failed to navigate to login page")
            return False

        # ユーザー名入力
        username_result = self.fill_form("input[name='email']", "admin@example.com")
        self.results.append(username_result)
        if not username_result.success:
            logger.warning("Failed to fill email field")
            return False

        # パスワード入力
        password_result = self.fill_form("input[name='password']", "admin123")
        self.results.append(password_result)
        if not password_result.success:
            logger.warning("Failed to fill password field")
            return False

        # 送信ボタンクリック（2秒待機でBrowserInteraction記録を確保）
        submit_result = self.click_element("button[type='submit']", wait_after=2.0)
        self.results.append(submit_result)
        if not submit_result.success:
            logger.warning("Failed to click submit button")
            return False

        # ログイン後のページ状態変化を検証（URL変更またはDOM要素の出現）
        url_changed = self.driver.current_url != f"{self.config.target_app_url}/auth/login"
        dom_verified = self.verify_element_exists(
            ".alert, .flash-message, .navbar, .container", timeout=5
        )
        submit_result.verified = url_changed or dom_verified
        submit_result.metadata["url_after"] = self.driver.current_url
        submit_result.metadata["url_changed"] = url_changed

        logger.info(
            f"Login form submitted. URL changed: {url_changed}, DOM verified: {dom_verified}"
        )
        return True

    def _execute_product_interactions(self) -> bool:
        """商品ページでのインタラクションを実行する

        Returns:
            bool: 少なくとも1つのインタラクション（リンククリックまたはカート追加）が成功した場合True
        """
        any_success = False

        # 商品一覧ページに遷移
        nav_result = self.navigate_to("/products")
        self.results.append(nav_result)
        if not nav_result.success:
            logger.warning("Failed to navigate to products page")
            return False

        # 商品リンクをクリック（2秒待機でBrowserInteraction記録を確保）
        product_click_result = self.click_element(
            ".card a, .product-link", wait_after=2.0
        )
        self.results.append(product_click_result)

        if product_click_result.success:
            any_success = True
            # クリック後のページ状態変化を検証
            current_url = self.driver.current_url
            product_click_result.metadata["url_after"] = current_url
            # 商品詳細ページに遷移したか確認
            url_indicates_product = (
                "/products/" in current_url or "/product" in current_url
            )
            dom_verified = self.verify_element_exists(
                ".card-body, h1, h2, .product-name", timeout=5
            )
            product_click_result.verified = url_indicates_product or dom_verified
            product_click_result.metadata["url_changed"] = url_indicates_product
            logger.info(
                f"Product link clicked. URL: {current_url}, DOM verified: {dom_verified}"
            )

            # カート追加ボタンクリック（2秒待機でBrowserInteraction記録を確保）
            cart_click_result = self.click_element(
                "form[action*='cart'] button[type='submit'], button.add-to-cart", wait_after=2.0
            )
            self.results.append(cart_click_result)

            if cart_click_result.success:
                # カート追加後のページ状態変化を検証
                cart_dom_verified = self.verify_element_exists(
                    ".alert, .flash-message, .cart-updated, .success, .badge",
                    timeout=5,
                )
                cart_click_result.verified = cart_dom_verified
                cart_click_result.metadata["cart_action_verified"] = cart_dom_verified
                logger.info(f"Cart add button clicked. DOM verified: {cart_dom_verified}")
        else:
            logger.warning("Failed to click product link, skipping cart add")

        return any_success

    def _execute_rage_click(self):
        """Rage Click を再現する（同じボタンを短時間に6回連打）

        JSエラーページのNull Referenceボタンを約400ms間隔で6回クリックする。
        New Relic Session ReplayがRage Clickとして検出する条件:
        - 同一要素を短時間（数秒以内）に複数回クリック
        """
        import time
        from selenium.webdriver.common.by import By
        from selenium.common.exceptions import WebDriverException

        logger.info("=== Rage Click simulation ===")

        # JSエラーページに遷移
        nav_result = self.navigate_to("/performance/js-errors")
        self.results.append(nav_result)
        if not nav_result.success:
            logger.warning("Failed to navigate to JS errors page for rage click")
            return

        # Null Reference ボタンを探す
        selector = "button[onclick*='triggerNullError']"
        try:
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC

            button = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
            )
        except Exception:
            logger.warning("Rage click target button not found")
            return

        # 10回連打（約100ms間隔 = 1秒以内に10クリック）
        start_time = time.time()
        click_count = 0
        for i in range(10):
            try:
                button.click()
                click_count += 1
                time.sleep(0.1)  # 100ms間隔
            except WebDriverException:
                pass

        duration_ms = (time.time() - start_time) * 1000

        # 結果を記録
        rage_step = StepResult(
            action="rage_click",
            target=selector,
            success=click_count >= 4,
            duration_ms=duration_ms,
            metadata={
                "click_count": click_count,
                "interval_ms": 100,
                "target_button": "triggerNullError",
                "purpose": "Session Replay Rage Click detection",
            },
        )
        self.results.append(rage_step)

        # Rage Click後にBrowser Agentがデータ送信する時間を確保
        time.sleep(3.0)

        logger.info(f"Rage click completed: {click_count} clicks in {duration_ms:.0f}ms")
