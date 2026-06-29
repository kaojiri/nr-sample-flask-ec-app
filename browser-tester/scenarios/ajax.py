"""AJAXリクエスト＋分散トレーシングテストシナリオ

分散トレーシングデモページで以下のバックエンド操作を実ブラウザから実行し、
Browser → Flask EC App → Flask-EC-Distributed-Service の分散トレースを生成する:

1. N+1クエリ問題の再現
2. Slow Query（pg_sleep, complex_join, cartesian_product）の再現
3. データベースエラー（syntax, constraint, connection, timeout）の再現
4. JSエラーページでのNetwork Errorトリガー

各操作後に十分な待機時間を設け、New Relic Browser Agent と APM Agent の
データ送信を確保する。
"""

import logging
from typing import List, Tuple

from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException

from scenarios.base import BaseScenario
from scenario_engine import register_scenario
from models import ScenarioResult, StepResult, TestStatus

logger = logging.getLogger(__name__)


@register_scenario
class AjaxScenario(BaseScenario):
    """分散トレーシング＋DB問題再現によるAjaxRequestイベント生成"""

    name = "ajax"
    description = "分散トレーシング経由でN+1/SlowQuery/DBエラーを再現しAjaxRequestを生成"

    def execute(self) -> ScenarioResult:
        """AJAXリクエストシナリオを実行

        1. ログイン
        2. N+1クエリ問題の実行（limit=50で多数のクエリ発行）
        3. Slow Query の実行（pg_sleep 3秒 + complex_join）
        4. データベースエラーの実行（全4タイプ）
        5. JSエラーページでのNetwork Error

        Returns:
            ScenarioResult: シナリオ実行結果
        """
        ajax_request_count = 0

        # --- ログイン ---
        if not self._login():
            return ScenarioResult(
                name=self.name,
                status=TestStatus.FAILED,
                steps=self.results,
                error_message="Login failed",
                expected_events={"AjaxRequest": 0},
            )

        # --- 分散トレーシングページへ遷移 ---
        nav_step = self.navigate_to("/distributed/")
        self.results.append(nav_step)

        if not nav_step.success:
            logger.error("Failed to navigate to distributed page")
            return ScenarioResult(
                name=self.name,
                status=TestStatus.FAILED,
                steps=self.results,
                error_message="Failed to navigate to distributed tracing page",
                expected_events={"AjaxRequest": 0},
            )

        # --- 1. N+1クエリ問題 ---
        logger.info("=== N+1 Query Problem ===")
        count = self._execute_n_plus_one(limit=50)
        ajax_request_count += count

        # --- 2. Slow Query ---
        logger.info("=== Slow Query ===")
        count = self._execute_slow_query(sleep_duration=3.0, query_type="sleep")
        ajax_request_count += count

        count = self._execute_slow_query(sleep_duration=2.0, query_type="complex_join")
        ajax_request_count += count

        # --- 3. Database Errors (全4タイプ) ---
        logger.info("=== Database Errors ===")
        for error_type in ["syntax", "constraint", "connection", "timeout"]:
            count = self._execute_database_error(error_type)
            ajax_request_count += count

        # --- 4. JSエラーページでのNetwork Error ---
        logger.info("=== Network Error (JS) ===")
        count = self._execute_network_error()
        ajax_request_count += count

        # ステータス判定
        status = TestStatus.COMPLETED if ajax_request_count > 0 else TestStatus.FAILED

        return ScenarioResult(
            name=self.name,
            status=status,
            steps=self.results,
            expected_events={"AjaxRequest": ajax_request_count},
            error_message=None if ajax_request_count > 0
            else "No AJAX requests were triggered",
        )

    def _login(self) -> bool:
        """テスト用アカウントでログイン"""
        logger.info("Logging in for AJAX scenario...")
        nav = self.navigate_to("/auth/login")
        self.results.append(nav)
        if not nav.success:
            return False

        fill1 = self.fill_form("input[name='email']", "admin@example.com")
        self.results.append(fill1)
        fill2 = self.fill_form("input[name='password']", "admin123")
        self.results.append(fill2)
        click = self.click_element("button[type='submit']", wait_after=2.0)
        self.results.append(click)

        return fill1.success and fill2.success and click.success

    def _execute_n_plus_one(self, limit: int = 50) -> int:
        """N+1クエリ問題を実行（パラメータ設定付き）"""
        try:
            # limitフィールドに値をセット
            self._set_input_value("#nPlusOneLimit", str(limit))

            # N+1クエリ実行ボタンをクリック
            click_step = self.click_element(
                "button[onclick*='callNPlusOne']", wait_after=5.0
            )
            click_step.page_name = f"N+1クエリ (limit={limit})"
            click_step.metadata = {
                "operation": "n_plus_one",
                "limit": limit,
                "backend_service": "Flask-EC-Distributed-Service",
                "expected_queries": f"~{limit + 1} queries",
            }
            self.results.append(click_step)

            if click_step.success:
                logger.info(f"N+1 query executed with limit={limit}")
                return 1
            return 0
        except Exception as e:
            logger.error(f"Error executing N+1 query: {e}")
            return 0

    def _execute_slow_query(self, sleep_duration: float = 3.0,
                            query_type: str = "sleep") -> int:
        """Slow Queryを実行（パラメータ設定付き）"""
        try:
            # sleepDurationフィールドに値をセット
            self._set_input_value("#sleepDuration", str(sleep_duration))

            # queryTypeセレクトボックスを変更
            self._set_select_value("#queryType", query_type)

            # 待機時間はsleep_duration + 余裕3秒
            wait_time = max(sleep_duration + 3.0, 5.0)

            # スロークエリ実行ボタンをクリック
            click_step = self.click_element(
                "button[onclick*='callSlowQuery']", wait_after=wait_time
            )
            click_step.page_name = f"SlowQuery ({query_type}, {sleep_duration}s)"
            click_step.metadata = {
                "operation": "slow_query",
                "query_type": query_type,
                "sleep_duration": sleep_duration,
                "backend_service": "Flask-EC-Distributed-Service",
            }
            self.results.append(click_step)

            if click_step.success:
                logger.info(
                    f"Slow query executed: type={query_type}, duration={sleep_duration}s"
                )
                return 1
            return 0
        except Exception as e:
            logger.error(f"Error executing slow query: {e}")
            return 0

    def _execute_database_error(self, error_type: str) -> int:
        """データベースエラーを実行"""
        try:
            # errorTypeセレクトボックスを変更
            self._set_select_value("#errorType", error_type)

            # データベースエラー実行ボタンをクリック
            click_step = self.click_element(
                "button[onclick*='callDatabaseError']", wait_after=5.0
            )
            click_step.page_name = f"DBエラー ({error_type})"
            click_step.metadata = {
                "operation": "database_error",
                "error_type": error_type,
                "backend_service": "Flask-EC-Distributed-Service",
                "expected_result": "500 error from distributed service",
            }
            self.results.append(click_step)

            if click_step.success:
                logger.info(f"Database error executed: type={error_type}")
                return 1
            return 0
        except Exception as e:
            logger.error(f"Error executing database error ({error_type}): {e}")
            return 0

    def _execute_network_error(self) -> int:
        """JSエラーページでNetwork Errorをトリガー"""
        nav_step = self.navigate_to("/performance/js-errors")
        self.results.append(nav_step)

        if not nav_step.success:
            return 0

        click_step = self.click_element(
            "button[onclick*='triggerNetworkError']", wait_after=3.0
        )
        click_step.page_name = "Network Error (fetch API failure)"
        click_step.metadata = {
            "operation": "network_error",
            "expected_result": "fetch API 500 error",
        }
        self.results.append(click_step)

        # triggerNetworkErrorはJS例外をthrowするが、
        # fetch自体は発行されるのでAjaxRequestは記録される
        if click_step.success or click_step.duration_ms > 1000:
            return 1
        return 0

    def _set_input_value(self, selector: str, value: str):
        """input要素の値をJavaScript経由で設定"""
        try:
            self.driver.execute_script(
                f"var el = document.querySelector('{selector}');"
                f"if (el) {{ el.value = '{value}'; }}"
            )
        except WebDriverException as e:
            logger.warning(f"Failed to set input value for {selector}: {e}")

    def _set_select_value(self, selector: str, value: str):
        """select要素の値をJavaScript経由で設定"""
        try:
            self.driver.execute_script(
                f"var el = document.querySelector('{selector}');"
                f"if (el) {{ el.value = '{value}'; }}"
            )
        except WebDriverException as e:
            logger.warning(f"Failed to set select value for {selector}: {e}")
