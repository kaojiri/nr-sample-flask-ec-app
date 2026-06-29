"""ページナビゲーションテストシナリオ

ECサイトの主要ページ（トップページ、商品一覧、商品詳細、カート、ログイン、会員登録）
に順次アクセスし、各ページのPageViewイベントがNew Relicに記録されるようにする。

各ページでDOM要素の存在確認とロード時間の記録を行い、
ページ間に2秒以上の待機時間を設けてBrowser Agentのデータ送信を確保する。
"""

import logging
from typing import List, Tuple

from models import ScenarioResult, StepResult, TestStatus
from scenario_engine import register_scenario
from scenarios.base import BaseScenario

logger = logging.getLogger(__name__)


@register_scenario
class NavigationScenario(BaseScenario):
    """主要ページへの順次ナビゲーション（PageView生成）"""

    name = "navigation"
    description = "主要ページへの順次ナビゲーション（PageView生成）"

    # (パス, ページ名, 検証用CSSセレクタ)
    PAGES: List[Tuple[str, str, str]] = [
        ("/", "トップページ", "h1, .navbar-brand"),
        ("/products", "商品一覧", ".product-list, .card"),
        ("/products/1", "商品詳細", ".card-body, h1"),
        ("/auth/login", "ログイン", "form, input[name='email']"),
        ("/auth/register", "会員登録", "form, input[name='username']"),
        ("/performance/js-errors", "JSエラーデモ", "button[onclick*='triggerNullError']"),
    ]

    def execute(self) -> ScenarioResult:
        """全主要ページに順次アクセスし、PageViewイベントを生成する。

        各ページで:
        1. ページ遷移（navigate_to で2秒以上の待機が保証される）
        2. DOM要素の存在確認
        3. ロード時間の記録

        Returns:
            ScenarioResult: シナリオ実行結果。
                いずれかのページでクリティカルな失敗（メインページが見つからない等）があれば
                status=FAILED、それ以外はCOMPLETED。
        """
        has_critical_failure = False

        for path, page_name, verify_selector in self.PAGES:
            logger.info(f"Navigating to {page_name} ({path})")

            # ページ遷移（navigate_to内で最低2秒の待機が保証される）
            step = self.navigate_to(path)
            step.page_name = page_name

            if step.success:
                # DOM要素の存在確認
                step.verified = self.verify_element_exists(verify_selector)
                # ロード時間は navigate_to 内で既に記録されるが、
                # 念のため検証結果が取れなかった場合の再取得
                if step.load_time_ms is None:
                    step.load_time_ms = self.get_page_load_time()

                if not step.verified:
                    logger.warning(
                        f"Page '{page_name}' loaded but element "
                        f"'{verify_selector}' not found"
                    )
            else:
                # ページ遷移自体が失敗した場合
                step.verified = False
                has_critical_failure = True
                logger.error(
                    f"Failed to navigate to {page_name}: {step.error_message}"
                )

            self.results.append(step)

        # ステータスの決定: メインページ（トップページ）が失敗したらFAILED
        # その他のページ失敗でもFAILEDとする
        status = TestStatus.FAILED if has_critical_failure else TestStatus.COMPLETED

        return ScenarioResult(
            name=self.name,
            status=status,
            steps=self.results,
            expected_events={"PageView": len(self.PAGES)},
        )
