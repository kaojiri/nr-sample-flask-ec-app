"""JavaScriptエラー検出テストシナリオ

JSエラーデモページ（/performance/js-errors）にアクセスし、
各エラートリガーボタンを順次クリックしてJavaScriptErrorイベントを生成する。

各ボタンクリック後にブラウザコンソールログからJSエラー発生を確認し、
エラー種別とSEVEREレベルエントリ数をメタデータに記録する。
"""

import logging
from typing import List, Tuple

from selenium.common.exceptions import WebDriverException

from models import ScenarioResult, StepResult, TestStatus
from scenario_engine import register_scenario
from scenarios.base import BaseScenario

logger = logging.getLogger(__name__)


@register_scenario
class JsErrorsScenario(BaseScenario):
    """JSエラートリガーによるJavaScriptErrorイベント生成"""

    name = "js_errors"
    description = "JSエラートリガーによるJavaScriptErrorイベント生成"

    # (CSSセレクタ, エラー名)
    ERROR_BUTTONS: List[Tuple[str, str]] = [
        ("button[onclick*='triggerNullError']", "Null Reference"),
        ("button[onclick*='triggerUndefinedFunctionError']", "Undefined Function"),
        ("button[onclick*='triggerPromiseRejection']", "Promise Rejection"),
        ("button[onclick*='triggerAsyncError']", "Async Error"),
        ("button[onclick*='triggerNetworkError']", "Network Error"),
        ("button[onclick*='triggerCustomError']", "Custom Error"),
    ]

    def execute(self) -> ScenarioResult:
        """JSエラーデモページで各エラートリガーボタンをクリックし、
        JavaScriptErrorイベントを生成する。

        各ボタンクリック後に:
        1. 2秒以上の待機（Browser AgentがJavaScriptError_Eventを送信する時間を確保）
        2. ブラウザコンソールログからSEVEREレベルエントリを検出
        3. エラー種別名とエラー数をメタデータに記録

        Returns:
            ScenarioResult: シナリオ実行結果。
                ナビゲーション成功かつ少なくとも一部のボタンがクリックできればCOMPLETED。
        """
        # JSエラーデモページへ遷移
        nav_step = self.navigate_to("/performance/js-errors")
        self.results.append(nav_step)

        if not nav_step.success:
            logger.error(
                f"Failed to navigate to /performance/js-errors: {nav_step.error_message}"
            )
            return ScenarioResult(
                name=self.name,
                status=TestStatus.FAILED,
                steps=self.results,
                error_message="Failed to navigate to JS errors page",
                expected_events={"JavaScriptError": len(self.ERROR_BUTTONS)},
            )

        buttons_clicked = 0

        for selector, error_name in self.ERROR_BUTTONS:
            logger.info(f"Triggering JS error: {error_name}")

            # ボタンをクリック（最低2秒の待機を指定）
            click_step = self.click_element(selector, wait_after=2.0)

            # ブラウザコンソールログからエラーを確認
            console_errors = self._get_browser_console_errors()

            # メタデータにエラー種別とSEVEREエントリ数を記録
            step = StepResult(
                action="trigger_error",
                target=error_name,
                success=click_step.success,
                duration_ms=click_step.duration_ms,
                error_message=click_step.error_message,
                metadata={
                    "error_type": error_name,
                    "console_errors": console_errors,
                    "selector": selector,
                },
            )

            if click_step.success:
                buttons_clicked += 1
            else:
                logger.warning(
                    f"Failed to click error button '{error_name}': "
                    f"{click_step.error_message}"
                )

            self.results.append(step)

        # ステータス決定: ナビゲーション成功かつ少なくとも一部のボタンがクリックできればCOMPLETED
        if buttons_clicked > 0:
            status = TestStatus.COMPLETED
        else:
            status = TestStatus.FAILED

        # --- Rage Click: 同じボタンを高速連打してSession Replayで検出させる ---
        self._execute_rage_click()

        return ScenarioResult(
            name=self.name,
            status=status,
            steps=self.results,
            expected_events={"JavaScriptError": len(self.ERROR_BUTTONS)},
        )

    def _execute_rage_click(self):
        """Rage Click を再現する（同じボタンを1秒以内に10回連打）

        既に /performance/js-errors ページにいる状態で、
        Null Referenceボタンを約100ms間隔で10回クリックする。
        New Relic Session ReplayがRage Clickとして検出する。
        """
        import time

        logger.info("=== Rage Click simulation (on JS errors page) ===")

        selector = "button[onclick*='triggerNullError']"
        try:
            from selenium.webdriver.common.by import By
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
                time.sleep(0.1)
            except WebDriverException:
                pass

        duration_ms = (time.time() - start_time) * 1000

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

        # Browser Agentがデータ送信する時間を確保
        time.sleep(3.0)

        logger.info(f"Rage click completed: {click_count} clicks in {duration_ms:.0f}ms")

    def _get_browser_console_errors(self) -> int:
        """ブラウザコンソールログからSEVEREレベルエントリ数を取得する。

        get_log('browser') はWebDriverExceptionを投げる場合があるため
        グレースフルにハンドリングし、取得できない場合は0を返す。

        Returns:
            int: SEVEREレベルのコンソールログエントリ数
        """
        try:
            logs = self.driver.get_log("browser")
            severe_count = len([l for l in logs if l.get("level") == "SEVERE"])
            return severe_count
        except WebDriverException as e:
            logger.warning(f"Could not retrieve browser console logs: {e}")
            return 0
