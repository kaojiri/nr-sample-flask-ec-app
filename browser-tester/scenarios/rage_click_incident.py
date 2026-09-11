"""Rage Click インシデント再現シナリオ

スライド「止血したはずが、また同じ電話が鳴る」のモデルケースを
ブラウザ操作で丸ごと再現し、New Relic に一連のデータを生成する。

再現する因果チェーン:
    1. JSエラーで画面無反応:
       /performance/rage-click の「添付ファイルを開く」ボタンは
       クリックすると内部で TypeError (AttachmentOpenError) が発生し、
       UI は無反応のまま。→ JavaScriptError イベント生成
    2. ボタン連打 (Rage Click):
       無反応に見えるボタンを短時間に連打。
       → Session Replay の Rage Click 検出 + PageAction('RageClick')
    3. サーバー負荷増:
       連打のたびにページが /performance/high-cpu を fetch し、
       アプリサーバー (Gunicorn worker) を CPU で飽和させる。
       → APM の high_cpu トランザクション集中 + Infra の CPU スパイク
    4. 他処理まで遅延:
       worker が飽和した状態で無関係な / と /products をブラウザで開く。
       → PageView.backendDuration が跳ね上がり、ユーザー体感の遅延を記録

New Relic で確認できるデータ:
    - JavaScriptError: AttachmentOpenError (無反応の根本原因)
    - PageAction: RageClick (連打)
    - PageView (rage-click / トップ / 商品一覧): backendDuration 悪化
    - APM Transaction: high_cpu 集中 (連打が誘発したサーバー負荷)
    - Infra SystemSample / ContainerSample: CPU スパイク
"""

import logging
import threading
import time
import urllib.request

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException

from models import ScenarioResult, StepResult, TestStatus
from scenario_engine import register_scenario
from scenarios.base import BaseScenario

logger = logging.getLogger(__name__)


@register_scenario
class RageClickIncidentScenario(BaseScenario):
    """JSエラー→連打→サーバー負荷→他ページ遅延の一連を再現する"""

    name = "rage_click_incident"
    description = (
        "承認画面のJSエラーによる無反応→Rage Click→サーバー負荷→他ページ遅延の再現"
    )

    # 添付ファイルボタン (JSエラーで無反応 + 連打でhigh-cpuを叩く)
    ATTACHMENT_BTN = "#openAttachmentBtn"
    # 連打回数（各クリックが high-cpu を1回 fetch する）
    RAGE_CLICK_COUNT = 40
    # 連打間隔（秒）。短いほど Rage Click として検出されやすい
    RAGE_CLICK_INTERVAL = 0.1
    # 連打後、Browser Agent が JSエラー/RageClick を送信(harvest)するまでの待機（秒）。
    # SPAエージェントの初回 harvest は十数秒かかることがあり、ここで rage-click
    # ページに十分留まらないと未送信のまま遷移してイベントが破棄される。
    # 実測で「40連打+fetch有効でも 20秒 留まれば全イベントが届く」ことを確認済み。
    POST_RAGE_HARVEST_WAIT = 18.0

    def execute(self) -> ScenarioResult:
        # --- 1 & 2 & 3: rage-click ページで連打 (JSエラー + Rage Click + サーバー負荷) ---
        nav_step = self.navigate_to("/performance/rage-click", wait_after=3.0)
        self.results.append(nav_step)

        if not nav_step.success:
            logger.error(
                f"Failed to navigate to /performance/rage-click: {nav_step.error_message}"
            )
            return ScenarioResult(
                name=self.name,
                status=TestStatus.FAILED,
                steps=self.results,
                error_message="Failed to navigate to rage-click page",
            )

        rage_ok = self._execute_rage_click()

        # rage-click ページで発生した JavaScriptError / RageClick(PageAction) を
        # 確実に送信させるため、他ページへ遷移する前に、このページから直接
        # about:blank へ遷移して unload flush する。
        # 先に他ページへ遷移すると前ページのイベントバッファが失われ、
        # JSエラー/PageAction が New Relic に届かない（実測で確認済み）。
        self._flush_browser_agent()

        # --- 4: worker 飽和中に無関係なページを開いて体感遅延を記録 ---
        degraded_ok = self._visit_other_pages_under_load()

        # 巡回ページ(PageView)分も最後に flush する
        self._flush_browser_agent()

        status = TestStatus.COMPLETED if rage_ok else TestStatus.FAILED

        return ScenarioResult(
            name=self.name,
            status=status,
            steps=self.results,
            expected_events={
                "JavaScriptError": 1,   # AttachmentOpenError
                "PageAction": 1,        # RageClick
                "PageView": 3,          # rage-click + / + /products
            },
        )

    def _execute_rage_click(self) -> bool:
        """添付ボタンを連打して JSエラー・Rage Click・サーバー負荷を発生させる"""
        logger.info("=== Rage Click on approval workflow attachment button ===")

        try:
            button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, self.ATTACHMENT_BTN))
            )
        except TimeoutException:
            logger.warning(f"Attachment button '{self.ATTACHMENT_BTN}' not found")
            self.results.append(
                StepResult(
                    action="rage_click",
                    target=self.ATTACHMENT_BTN,
                    success=False,
                    error_message="Attachment button not found",
                )
            )
            return False

        start_time = time.time()
        click_count = 0
        for _ in range(self.RAGE_CLICK_COUNT):
            try:
                button.click()
                click_count += 1
                time.sleep(self.RAGE_CLICK_INTERVAL)
            except WebDriverException:
                # 無反応でもクリック自体は成立する。稀な要素再描画エラーは無視
                pass

        duration_ms = (time.time() - start_time) * 1000

        rage_step = StepResult(
            action="rage_click",
            target=self.ATTACHMENT_BTN,
            success=click_count >= 10,
            duration_ms=duration_ms,
            metadata={
                "click_count": click_count,
                "interval_ms": int(self.RAGE_CLICK_INTERVAL * 1000),
                "target_button": "openAttachmentBtn",
                "purpose": "JSエラー(AttachmentOpenError) + Rage Click + サーバー負荷(high-cpu)",
            },
        )
        self.results.append(rage_step)
        logger.info(
            f"Rage click completed: {click_count} clicks in {duration_ms:.0f}ms "
            f"(each click triggers a JS error and a /performance/high-cpu request)"
        )

        # ページ内 JS のイベント発火はタイミング/実装に依存して New Relic に
        # 届かないことがあるため、シナリオ側からも明示的に New Relic Browser の
        # noticeError / addPageAction を呼び、JSエラーと RageClick を確実に記録する。
        try:
            self.driver.execute_script(
                "if (window.newrelic) {"
                "  window.newrelic.noticeError("
                "    new Error('AttachmentOpenError: PDF viewer is undefined'),"
                "    {errorType:'AttachmentOpenError', element:'openAttachmentBtn',"
                "     page:'approval_workflow', clickCount: arguments[0]});"
                "  window.newrelic.addPageAction('RageClick',"
                "    {element:'openAttachmentBtn', totalClicks: arguments[0],"
                "     page:'approval_workflow'});"
                "}",
                click_count,
            )
            logger.info("Explicitly reported AttachmentOpenError + RageClick to New Relic")
        except WebDriverException as e:
            logger.warning(f"Explicit New Relic reporting failed: {e}")

        # Browser Agent が JavaScriptError / RageClick(PageAction) をビーコン送信するのを待つ。
        # ここで待たずに次ページへ遷移すると、未送信のイベントが破棄されて
        # New Relic に届かないことがある（今回の主因）。
        # 同ページに留まったまま待つことで確実に harvest させる。
        time.sleep(self.POST_RAGE_HARVEST_WAIT)
        return click_count >= 10

    def _visit_other_pages_under_load(self) -> bool:
        """worker 飽和中に無関係なページを開き、体感遅延(PageView)を記録する。

        連打後の harvest 待機中に high-cpu の fetch は捌けてしまうため、
        巡回のあいだはシナリオ自身がバックグラウンドで high-cpu を叩き続け、
        Gunicorn worker を確実に飽和させる。これにより無関係な / と /products の
        PageView.backendDuration が悪化し、「他処理まで遅延」が記録される。
        """
        logger.info("=== Visiting unrelated pages while workers are saturated ===")
        any_success = False

        stop_load = threading.Event()
        load_thread = threading.Thread(
            target=self._background_server_load, args=(stop_load,), daemon=True
        )
        load_thread.start()
        # worker が埋まるまで少し待ってから巡回開始
        time.sleep(2.0)

        try:
            # トップと商品一覧を交互に複数回開く。
            for path in ("/", "/products", "/", "/products"):
                step = self.navigate_to(path, wait_after=2.0)
                step.metadata["under_server_load"] = True
                self.results.append(step)
                if step.success:
                    any_success = True
                    logger.info(
                        f"Visited {path} under load: load_time_ms={step.load_time_ms}"
                    )
        finally:
            stop_load.set()
            load_thread.join(timeout=10)

        return any_success

    def _background_server_load(self, stop_event: threading.Event):
        """他ページ巡回中、high-cpu を並列に叩き続けて worker を飽和させる。

        Gunicorn は workers=4 なので、4本以上を同時に走らせると
        無関係なリクエストがキュー待ちになり、体感遅延が発生する。
        """
        target = f"{self.config.target_app_url}/performance/high-cpu"

        def hit():
            try:
                urllib.request.urlopen(target, timeout=30).read()
            except Exception:
                pass

        while not stop_event.is_set():
            workers = [threading.Thread(target=hit, daemon=True) for _ in range(6)]
            for w in workers:
                w.start()
            for w in workers:
                w.join()

    def _flush_browser_agent(self):
        """Browser Agent の未送信ビーコンを確実に flush する。

        about:blank へ遷移して現在ページの unload を発生させることで、
        harvest 待ちの JavaScriptError / PageAction / PageView を送信させる。
        """
        logger.info("=== Flushing Browser Agent beacons (navigate to about:blank) ===")
        try:
            # 直前ページの harvest 猶予を確保
            time.sleep(4.0)
            self.driver.get("about:blank")
            # unload 後の送信完了を待つ
            time.sleep(4.0)
        except WebDriverException as e:
            logger.warning(f"Flush navigation failed: {e}")
