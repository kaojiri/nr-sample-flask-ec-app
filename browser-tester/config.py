"""環境変数ベースの設定パーサ

環境変数からRunnerConfigを生成する。
無効な値や未設定時にはデフォルト値にフォールバックする。
"""

import os
from models import RunnerConfig


# 有効なログレベル
VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def load_config_from_env() -> RunnerConfig:
    """環境変数からRunnerConfigを生成する。

    サポートする環境変数:
    - TARGET_APP_URL: テスト対象のアプリケーションURL
    - PAGE_WAIT_SECONDS: ページ間の待機時間（秒）
    - BROWSER_WIDTH: ブラウザウィンドウの幅（ピクセル）
    - BROWSER_HEIGHT: ブラウザウィンドウの高さ（ピクセル）
    - RETRY_COUNT: テスト失敗時のリトライ回数
    - PAGE_TIMEOUT_SECONDS: ページロードタイムアウト時間（秒）
    - LOG_LEVEL: ログレベル（DEBUG, INFO, WARNING, ERROR, CRITICAL）

    無効な値や未設定の場合はRunnerConfigのデフォルト値を使用する。
    """
    config = RunnerConfig()

    # TARGET_APP_URL: 空でない文字列であれば採用
    target_url = os.environ.get("TARGET_APP_URL")
    if target_url and target_url.strip():
        config.target_app_url = target_url.strip()

    # PAGE_WAIT_SECONDS: 正の浮動小数点数
    page_wait = os.environ.get("PAGE_WAIT_SECONDS")
    if page_wait is not None:
        try:
            val = float(page_wait)
            if val > 0:
                config.page_wait_seconds = val
        except (ValueError, TypeError):
            pass

    # BROWSER_WIDTH: 正の整数
    browser_width = os.environ.get("BROWSER_WIDTH")
    if browser_width is not None:
        try:
            val = int(browser_width)
            if val > 0:
                config.browser_width = val
        except (ValueError, TypeError):
            pass

    # BROWSER_HEIGHT: 正の整数
    browser_height = os.environ.get("BROWSER_HEIGHT")
    if browser_height is not None:
        try:
            val = int(browser_height)
            if val > 0:
                config.browser_height = val
        except (ValueError, TypeError):
            pass

    # RETRY_COUNT: 0以上の整数
    retry_count = os.environ.get("RETRY_COUNT")
    if retry_count is not None:
        try:
            val = int(retry_count)
            if val >= 0:
                config.retry_count = val
        except (ValueError, TypeError):
            pass

    # PAGE_TIMEOUT_SECONDS: 正の整数
    page_timeout = os.environ.get("PAGE_TIMEOUT_SECONDS")
    if page_timeout is not None:
        try:
            val = int(page_timeout)
            if val > 0:
                config.page_timeout_seconds = val
        except (ValueError, TypeError):
            pass

    # LOG_LEVEL: 有効なログレベル文字列
    log_level = os.environ.get("LOG_LEVEL")
    if log_level and log_level.strip().upper() in VALID_LOG_LEVELS:
        config.log_level = log_level.strip().upper()

    return config
