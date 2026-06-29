"""テストシナリオ基底クラス

全テストシナリオの共通操作（ページ遷移、要素クリック、フォーム入力、
要素存在確認、ページロード時間取得）を提供する抽象基底クラス。

各メソッドはStepResultを生成し、duration計測とエラーハンドリングを含む。
タイムアウト時はsuccess=Falseを返し、シナリオは次のステップに継続する。
"""

import time
from abc import ABC, abstractmethod
from typing import List, Optional

from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    WebDriverException,
)

from models import StepResult, ScenarioResult, RunnerConfig


class BaseScenario(ABC):
    """テストシナリオの基底クラス"""

    name: str  # シナリオ識別名
    description: str  # 説明

    def __init__(self, driver: WebDriver, config: RunnerConfig):
        self.driver = driver
        self.config = config
        self.results: List[StepResult] = []

    @abstractmethod
    def execute(self) -> ScenarioResult:
        """シナリオを実行し結果を返す"""
        ...

    def navigate_to(self, path: str, wait_after: Optional[float] = None) -> StepResult:
        """ページ遷移 + Browser Agent送信待機

        Args:
            path: 遷移先のパス（target_app_urlに結合される）
            wait_after: 遷移後の待機時間（秒）。Noneの場合はconfig.page_wait_secondsを使用。
                        最低2秒が保証される。

        Returns:
            StepResult: 遷移結果（success=Falseの場合はタイムアウトエラー）
        """
        url = f"{self.config.target_app_url}{path}"
        wait_time = wait_after if wait_after is not None else self.config.page_wait_seconds
        # 最低2秒の待機時間を保証（Requirements 2.2）
        wait_time = max(wait_time, 2.0)

        start_time = time.time()
        try:
            self.driver.get(url)
            time.sleep(wait_time)
            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000

            # ページロード時間を記録
            load_time = self.get_page_load_time()

            return StepResult(
                action="navigate",
                target=path,
                success=True,
                duration_ms=duration_ms,
                load_time_ms=load_time,
            )
        except TimeoutException as e:
            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000
            return StepResult(
                action="navigate",
                target=path,
                success=False,
                duration_ms=duration_ms,
                error_message=f"Timeout navigating to {path}: {str(e)}",
            )
        except WebDriverException as e:
            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000
            return StepResult(
                action="navigate",
                target=path,
                success=False,
                duration_ms=duration_ms,
                error_message=f"WebDriver error navigating to {path}: {str(e)}",
            )

    def click_element(self, selector: str, wait_after: float = 1.0) -> StepResult:
        """要素クリック + 待機

        Args:
            selector: CSSセレクタ
            wait_after: クリック後の待機時間（秒）。最低1秒が保証される。

        Returns:
            StepResult: クリック結果（success=Falseの場合はタイムアウトまたはエラー）
        """
        # 最低1秒の待機時間を保証（Requirements 3.4）
        wait_after = max(wait_after, 1.0)

        start_time = time.time()
        try:
            element = WebDriverWait(self.driver, self.config.page_timeout_seconds).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
            )
            element.click()
            time.sleep(wait_after)
            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000

            return StepResult(
                action="click",
                target=selector,
                success=True,
                duration_ms=duration_ms,
            )
        except TimeoutException as e:
            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000
            return StepResult(
                action="click",
                target=selector,
                success=False,
                duration_ms=duration_ms,
                error_message=f"Timeout waiting for clickable element '{selector}': {str(e)}",
            )
        except WebDriverException as e:
            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000
            return StepResult(
                action="click",
                target=selector,
                success=False,
                duration_ms=duration_ms,
                error_message=f"WebDriver error clicking '{selector}': {str(e)}",
            )

    def fill_form(self, selector: str, value: str) -> StepResult:
        """フォーム入力

        Args:
            selector: CSSセレクタ
            value: 入力する値

        Returns:
            StepResult: 入力結果
        """
        start_time = time.time()
        try:
            element = self.driver.find_element(By.CSS_SELECTOR, selector)
            element.clear()
            element.send_keys(value)
            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000

            return StepResult(
                action="fill",
                target=selector,
                success=True,
                duration_ms=duration_ms,
            )
        except (NoSuchElementException, WebDriverException) as e:
            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000
            return StepResult(
                action="fill",
                target=selector,
                success=False,
                duration_ms=duration_ms,
                error_message=f"Error filling form element '{selector}': {str(e)}",
            )

    def verify_element_exists(self, selector: str, timeout: int = 10) -> bool:
        """DOM要素の存在確認

        Args:
            selector: CSSセレクタ
            timeout: 待機タイムアウト（秒）

        Returns:
            bool: 要素が存在すればTrue、タイムアウトならFalse
        """
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            return True
        except TimeoutException:
            return False

    def get_page_load_time(self) -> Optional[float]:
        """Navigation Timing APIからページロード時間を取得

        Returns:
            float: ページロード時間（ミリ秒）。取得できない場合や負の値の場合はNone。
        """
        try:
            load_time = self.driver.execute_script(
                "return window.performance.timing.loadEventEnd - "
                "window.performance.timing.navigationStart"
            )
            if load_time is None or load_time < 0:
                return None
            return float(load_time)
        except WebDriverException:
            return None
