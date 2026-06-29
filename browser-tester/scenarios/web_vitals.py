"""Core Web Vitals テストシナリオ

パフォーマンス問題ページにアクセスし、Core Web Vitals データを生成する。
/performance/bad-vitals ページで高LCP・高CLSを発生させ、
/performance/slow ページで高レスポンスタイムのPageViewを生成する。

各ページのDOM Content Loaded時間とLoad Complete時間をメタデータとして記録する。
"""

import logging

from selenium.common.exceptions import WebDriverException

from models import ScenarioResult, StepResult, TestStatus
from scenario_engine import register_scenario
from scenarios.base import BaseScenario

logger = logging.getLogger(__name__)


@register_scenario
class WebVitalsScenario(BaseScenario):
    """パフォーマンス問題ページアクセスによるCore Web Vitalsデータ生成"""

    name = "web_vitals"
    description = "パフォーマンス問題ページアクセスによるCore Web Vitalsデータ生成"

    def execute(self) -> ScenarioResult:
        """パフォーマンス問題ページにアクセスし、Core Web Vitalsデータを生成する。

        1. /performance/bad-vitals ページにアクセスし5秒以上待機（CWVデータ収集用）
        2. /performance/slow ページにアクセスし8秒以上待機（高レスポンスタイム生成）
        3. 各ページのDOM Content Loaded時間とLoad Complete時間を記録

        Returns:
            ScenarioResult: シナリオ実行結果。
                両ページのアクセスが成功すればCOMPLETED、いずれかが失敗すればFAILED。
        """
        has_failure = False

        # 1. Bad Vitalsページ（高LCP、高CLS）
        logger.info("Navigating to /performance/bad-vitals (high LCP, high CLS)")
        step_bad_vitals = self.navigate_to("/performance/bad-vitals", wait_after=5.0)
        step_bad_vitals.page_name = "Bad Vitals（高LCP・高CLS）"

        if step_bad_vitals.success:
            # DOM Content Loaded時間とLoad Complete時間を記録
            timing_data = self._get_timing_data()
            step_bad_vitals.metadata.update(timing_data)
        else:
            has_failure = True
            logger.error(
                f"Failed to navigate to /performance/bad-vitals: "
                f"{step_bad_vitals.error_message}"
            )

        self.results.append(step_bad_vitals)

        # 2. スローエンドポイント（高レスポンスタイム）
        logger.info("Navigating to /performance/slow (high response time)")
        step_slow = self.navigate_to("/performance/slow", wait_after=8.0)
        step_slow.page_name = "Slow Page（高レスポンスタイム）"

        if step_slow.success:
            # DOM Content Loaded時間とLoad Complete時間を記録
            timing_data = self._get_timing_data()
            step_slow.metadata.update(timing_data)
        else:
            has_failure = True
            logger.error(
                f"Failed to navigate to /performance/slow: "
                f"{step_slow.error_message}"
            )

        self.results.append(step_slow)

        # ステータスの決定
        status = TestStatus.FAILED if has_failure else TestStatus.COMPLETED

        return ScenarioResult(
            name=self.name,
            status=status,
            steps=self.results,
            expected_events={"PageView": 2},
        )

    def _get_timing_data(self) -> dict:
        """Navigation Timing APIからDOM Content Loaded時間とLoad Complete時間を取得する。

        Returns:
            dict: タイミングデータを含む辞書。取得に失敗した場合は空の値を含む。
                - "dom_content_loaded_ms": domContentLoadedEventEnd - navigationStart
                - "load_complete_ms": loadEventEnd - navigationStart
        """
        result = {
            "dom_content_loaded_ms": None,
            "load_complete_ms": None,
        }

        try:
            dom_content_loaded = self.driver.execute_script(
                "return window.performance.timing.domContentLoadedEventEnd - "
                "window.performance.timing.navigationStart"
            )
            if dom_content_loaded is not None and dom_content_loaded >= 0:
                result["dom_content_loaded_ms"] = float(dom_content_loaded)
        except WebDriverException as e:
            logger.warning(f"Failed to get DOM Content Loaded time: {e}")

        try:
            load_complete = self.driver.execute_script(
                "return window.performance.timing.loadEventEnd - "
                "window.performance.timing.navigationStart"
            )
            if load_complete is not None and load_complete >= 0:
                result["load_complete_ms"] = float(load_complete)
        except WebDriverException as e:
            logger.warning(f"Failed to get Load Complete time: {e}")

        return result
