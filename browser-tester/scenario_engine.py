"""シナリオ実行エンジン

テストシナリオの実行管理を行うコアコンポーネント。
ヘッドレスChromeドライバーの生成、シナリオの順次実行、
Browser Agentデータ送信待機を担当する。
"""

import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Type

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.common.exceptions import WebDriverException

from models import RunnerConfig, RunResult, ScenarioResult, TestStatus
from scenarios.base import BaseScenario

logger = logging.getLogger(__name__)

# シナリオレジストリ: シナリオ名からクラスへのマッピング
# 各シナリオモジュールが実装された段階でここに追加される
SCENARIO_REGISTRY: Dict[str, Type[BaseScenario]] = {}


def register_scenario(cls: Type[BaseScenario]) -> Type[BaseScenario]:
    """シナリオクラスをレジストリに登録するデコレータ"""
    SCENARIO_REGISTRY[cls.name] = cls
    return cls


def _load_scenarios():
    """利用可能なシナリオモジュールを遅延ロードする。

    ImportErrorは無視し、まだ実装されていないシナリオは
    レジストリに含めない。
    """
    scenario_modules = [
        "scenarios.navigation",
        "scenarios.interaction",
        "scenarios.ajax",
        "scenarios.js_errors",
        "scenarios.web_vitals",
        "scenarios.rage_click_incident",
        "scenarios.normal_baseline",
    ]
    for module_name in scenario_modules:
        try:
            __import__(module_name)
        except ImportError:
            logger.debug(f"Scenario module '{module_name}' not available, skipping.")


class ScenarioEngine:
    """テストシナリオの実行管理"""

    def __init__(self, config: RunnerConfig):
        self.config = config
        self.driver: Optional[WebDriver] = None

    def create_driver(self) -> WebDriver:
        """ヘッドレスChromeドライバーを生成

        Returns:
            WebDriver: 設定済みのChromeドライバーインスタンス
        """
        options = ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument(
            f"--window-size={self.config.browser_width},{self.config.browser_height}"
        )
        options.add_argument("--disable-web-security")  # CORS制限の回避

        # seleniarm/standalone-chromium ではchromedriver のパスを明示指定
        import shutil
        chromedriver_path = shutil.which("chromedriver") or "/usr/bin/chromedriver"
        service = ChromeService(executable_path=chromedriver_path)
        return webdriver.Chrome(service=service, options=options)

    def run_scenarios(self, scenario_names: List[str]) -> RunResult:
        """指定シナリオを順次実行しRunResultを生成

        Args:
            scenario_names: 実行するシナリオ名のリスト

        Returns:
            RunResult: 全シナリオの実行結果を含むRunResult
        """
        # シナリオモジュールの遅延ロード
        _load_scenarios()

        run_result = RunResult(
            status=TestStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
            config_used={
                "target_app_url": self.config.target_app_url,
                "page_wait_seconds": self.config.page_wait_seconds,
                "browser_width": self.config.browser_width,
                "browser_height": self.config.browser_height,
                "retry_count": self.config.retry_count,
            },
        )

        try:
            self.driver = self.create_driver()
            logger.info("Chrome WebDriver created successfully.")

            for i, scenario_name in enumerate(scenario_names):
                logger.info(f"Running scenario: {scenario_name}")

                scenario_cls = SCENARIO_REGISTRY.get(scenario_name)
                if scenario_cls is None:
                    logger.warning(
                        f"Scenario '{scenario_name}' not found in registry, skipping."
                    )
                    run_result.scenarios.append(
                        ScenarioResult(
                            name=scenario_name,
                            status=TestStatus.FAILED,
                            error_message=f"Scenario '{scenario_name}' not found in registry",
                        )
                    )
                    continue

                scenario_result = self._execute_scenario(scenario_cls)
                run_result.scenarios.append(scenario_result)

                # シナリオ間にBrowser Agent フラッシュ用の待機時間を挿入
                if i < len(scenario_names) - 1:
                    self.wait_for_browser_agent(2.0)

            # 最終ステータスを設定
            if any(s.status == TestStatus.FAILED for s in run_result.scenarios):
                run_result.status = TestStatus.FAILED
            else:
                run_result.status = TestStatus.COMPLETED

        except Exception as e:
            logger.error(f"Unexpected error during scenario execution: {e}")
            run_result.status = TestStatus.FAILED
        finally:
            if self.driver is not None:
                try:
                    self.driver.quit()
                    logger.info("Chrome WebDriver closed.")
                except Exception as e:
                    logger.warning(f"Error closing WebDriver: {e}")
                self.driver = None
            run_result.completed_at = datetime.now(timezone.utc)

        return run_result

    def _execute_scenario(self, scenario_cls: Type[BaseScenario]) -> ScenarioResult:
        """個別シナリオをリトライ付きで実行する

        失敗時にconfig.retry_count回までリトライする。
        途中で成功(COMPLETED)した場合は即座にその結果を返す。
        リトライ間に5秒の追加待機を挿入する。
        WebDriverException発生時はドライバーを再生成する。

        Args:
            scenario_cls: 実行するシナリオクラス

        Returns:
            ScenarioResult: シナリオ実行結果（retry_countフィールドにリトライ回数を記録）
        """
        start_time = time.time()
        last_result: Optional[ScenarioResult] = None

        for attempt in range(self.config.retry_count + 1):
            try:
                scenario = scenario_cls(driver=self.driver, config=self.config)
                result = scenario.execute()
                result.duration_seconds = time.time() - start_time
                result.retry_count = attempt

                if result.status == TestStatus.COMPLETED:
                    return result

                last_result = result
                logger.info(
                    f"Scenario '{scenario_cls.name}' did not complete "
                    f"(attempt {attempt + 1}/{self.config.retry_count + 1})"
                )
            except WebDriverException as e:
                logger.error(
                    f"WebDriverException in scenario '{scenario_cls.name}' "
                    f"(attempt {attempt + 1}/{self.config.retry_count + 1}): {e}"
                )
                last_result = ScenarioResult(
                    name=scenario_cls.name,
                    status=TestStatus.FAILED,
                    error_message=str(e),
                    retry_count=attempt,
                    duration_seconds=time.time() - start_time,
                )
                if attempt < self.config.retry_count:
                    time.sleep(5)  # リトライ前に追加待機
                    self._recreate_driver()
                continue
            except Exception as e:
                logger.error(
                    f"Unexpected error in scenario '{scenario_cls.name}' "
                    f"(attempt {attempt + 1}/{self.config.retry_count + 1}): {e}"
                )
                last_result = ScenarioResult(
                    name=scenario_cls.name,
                    status=TestStatus.FAILED,
                    error_message=str(e),
                    retry_count=attempt,
                    duration_seconds=time.time() - start_time,
                )

            # リトライ間に5秒の追加待機を挿入
            if attempt < self.config.retry_count:
                time.sleep(5)

        # 全リトライ後も成功しなかった場合
        last_result.retry_count = self.config.retry_count
        last_result.duration_seconds = time.time() - start_time
        return last_result

    def _recreate_driver(self):
        """WebDriverを再生成する

        現在のドライバーをquitし、新しいドライバーを生成する。
        WebDriverException発生後のリカバリに使用される。
        """
        logger.info("Recreating WebDriver...")
        if self.driver is not None:
            try:
                self.driver.quit()
            except Exception as e:
                logger.warning(f"Error quitting old driver during recreation: {e}")
        self.driver = self.create_driver()
        logger.info("WebDriver recreated successfully.")

    def wait_for_browser_agent(self, seconds: float):
        """Browser AgentのBeacon送信待機

        Args:
            seconds: 待機する秒数
        """
        logger.debug(f"Waiting {seconds}s for Browser Agent data flush...")
        time.sleep(seconds)
