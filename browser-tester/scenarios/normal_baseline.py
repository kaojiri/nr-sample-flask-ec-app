"""通常ベースライン負荷シナリオ

Rage Click インシデントのデモで「平常 → 異常」のコントラストを綺麗に出すための、
健全な平常時トラフィックを生成するシナリオ。

意図:
- 通常のユーザーがサイトを回遊するだけの、軽い正常系ページのみアクセスする
- 重い処理(/performance/*)やエラー系は一切叩かない → ベースラインが荒れない
- browser-tester のループ実行(例: 30分)でこのシナリオを回し続けると、
  トップ/商品一覧/商品詳細の PageView・Transaction が定常的に発生し、
  平らなベースラインができる
- そこに rage_click_incident シナリオを重ねると、CPUスパイク・JSエラー・
  他ページ遅延が「平常からの逸脱」としてくっきり見える

アクセスする正常系ページ:
- /            (トップ)
- /products    (商品一覧)
- /products/1  (商品詳細)
- /products/2  (商品詳細)
"""

import logging

from models import ScenarioResult, TestStatus
from scenario_engine import register_scenario
from scenarios.base import BaseScenario

logger = logging.getLogger(__name__)


@register_scenario
class NormalBaselineScenario(BaseScenario):
    """正常系ページのみを巡回して健全なベースライン負荷を生成する"""

    name = "normal_baseline"
    description = "正常系ページ(トップ/商品一覧/商品詳細)のみを巡回する平常時ベースライン負荷"

    # 巡回する正常系ページ（重い処理・エラー系は含めない）
    PAGES = [
        "/",
        "/products",
        "/products/1",
        "/products",
        "/products/2",
        "/",
    ]

    # 各ページ滞在時間（秒）。通常ユーザーの回遊を模した自然な間隔
    PAGE_DWELL_SECONDS = 2.0

    def execute(self) -> ScenarioResult:
        visited = 0

        for path in self.PAGES:
            step = self.navigate_to(path, wait_after=self.PAGE_DWELL_SECONDS)
            step.metadata["baseline"] = True
            self.results.append(step)
            if step.success:
                visited += 1
                logger.info(
                    f"[baseline] visited {path} (load_time_ms={step.load_time_ms})"
                )
            else:
                logger.warning(f"[baseline] failed to visit {path}: {step.error_message}")

        status = TestStatus.COMPLETED if visited > 0 else TestStatus.FAILED

        return ScenarioResult(
            name=self.name,
            status=status,
            steps=self.results,
            expected_events={"PageView": len(self.PAGES)},
        )
