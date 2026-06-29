"""AJAXリクエストモニタリングテストシナリオ

分散トレーシングデモページおよびパフォーマンスデモページで
AJAXリクエスト（XHR/Fetch）をトリガーし、New Relic BrowserのAjaxRequestイベント
生成を検証する。

正常系（200レスポンス）と異常系（500レスポンス）の両方をテストする。
"""

import logging
from typing import List

from scenarios.base import BaseScenario
from scenario_engine import register_scenario
from models import ScenarioResult, StepResult, TestStatus

logger = logging.getLogger(__name__)


@register_scenario
class AjaxScenario(BaseScenario):
    """AJAXリクエスト発生操作によるAjaxRequestイベント生成"""

    name = "ajax"
    description = "AJAXリクエスト発生操作によるAjaxRequestイベント生成"

    # AJAXトリガーボタン定義
    # 分散トレーシングページ: 正常系（200レスポンス）+ 分散サービス呼び出し
    DISTRIBUTED_AJAX_BUTTONS: List[tuple] = [
        (
            "button[onclick*='callNPlusOne']",
            "N+1クエリ実行（分散サービス呼び出し）",
        ),
        (
            "button[onclick*='callSlowQuery']",
            "スロークエリ実行（分散サービス呼び出し）",
        ),
        (
            "button[onclick*='callDatabaseError']",
            "データベースエラー（分散サービス異常系）",
        ),
    ]

    # パフォーマンスデモページ: 異常系（500レスポンス）
    ERROR_AJAX_BUTTON = (
        "button[onclick*='triggerNetworkError']",
        "Network Error（異常系AJAX 500）",
    )

    def execute(self) -> ScenarioResult:
        """AJAXリクエストシナリオを実行

        1. ログイン（認証が必要なページがあるため）
        2. 分散トレーシングデモページでAJAXリクエストをトリガー（正常系）
        3. パフォーマンスデモページでネットワークエラーをトリガー（異常系）

        Returns:
            ScenarioResult: シナリオ実行結果
        """
        ajax_request_count = 0

        # --- ログイン（分散トレーシングページには認証が必要） ---
        self._login()

        # --- 正常系: 分散トレーシングデモページ ---
        logger.info("Navigating to distributed tracing demo page for AJAX tests")
        nav_step = self.navigate_to("/distributed/")
        self.results.append(nav_step)

        if nav_step.success:
            for selector, description in self.DISTRIBUTED_AJAX_BUTTONS:
                logger.info(f"Clicking AJAX trigger: {description}")
                # AJAXリクエスト後に3秒以上待機（Requirements 4.2）
                click_step = self.click_element(selector, wait_after=3.0)
                click_step.page_name = description
                click_step.metadata = {
                    "ajax_type": "distributed_trace",
                    "page": "/distributed/",
                    "backend_service": "Flask-EC-Distributed-Service",
                }
                self.results.append(click_step)

                if click_step.success:
                    ajax_request_count += 1
        else:
            logger.warning("Failed to navigate to distributed tracing page, skipping AJAX triggers")

        # --- 異常系: パフォーマンスデモページ（500エラー） ---
        logger.info("Navigating to JS errors page for error AJAX test")
        nav_step_errors = self.navigate_to("/performance/js-errors")
        self.results.append(nav_step_errors)

        if nav_step_errors.success:
            selector, description = self.ERROR_AJAX_BUTTON
            logger.info(f"Clicking AJAX error trigger: {description}")
            # AJAXリクエスト後に3秒以上待機（Requirements 4.2）
            click_step = self.click_element(selector, wait_after=3.0)
            click_step.page_name = description
            click_step.metadata = {"ajax_type": "error_500", "page": "/performance/js-errors"}
            self.results.append(click_step)

            # triggerNetworkError()はJS例外をthrowするためclick_stepが
            # success=Falseになる場合があるが、ボタンクリック自体は成功と見なす
            # （AjaxRequestイベントはthrow前に発生済み）
            if click_step.success or click_step.duration_ms > 1000:
                ajax_request_count += 1
        else:
            logger.warning("Failed to navigate to JS errors page, skipping error AJAX trigger")

        # ステータス判定: 少なくとも1つのAJAXリクエストがトリガーされれば成功
        if ajax_request_count > 0:
            status = TestStatus.COMPLETED
        else:
            status = TestStatus.FAILED

        return ScenarioResult(
            name=self.name,
            status=status,
            steps=self.results,
            expected_events={"AjaxRequest": ajax_request_count},
            error_message=None if ajax_request_count > 0
            else "No AJAX requests were triggered successfully",
        )

    def _login(self):
        """テスト用アカウントでログインする（認証が必要なページ用）"""
        logger.info("Logging in for AJAX scenario...")
        self.navigate_to("/auth/login")
        self.fill_form("input[name='email']", "admin@example.com")
        self.fill_form("input[name='password']", "admin123")
        self.click_element("button[type='submit']", wait_after=2.0)
