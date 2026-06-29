"""Browser Test Runner Flask API

テスト実行の制御と結果取得を行うRESTful API。
同時実行排他制御、バックグラウンドスレッド実行、ヘルスチェックを提供する。
"""

import logging
import os
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

import requests as http_requests
from flask import Flask, jsonify, request

from config import load_config_from_env
from models import RunnerConfig, RunResult, TestStatus
from result_store import ResultStore
from scenario_engine import ScenarioEngine, SCENARIO_REGISTRY

# ログ設定: 標準出力への出力
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# 利用可能なシナリオ名
AVAILABLE_SCENARIOS = ["navigation", "interaction", "ajax", "js_errors", "web_vitals"]

# アプリ起動時刻
APP_START_TIME = time.time()

# グローバルな結果ストア
# Docker環境では /app/data/results、ローカルではカレントディレクトリ配下を使用
_results_dir = Path(os.environ.get("RESULTS_DIR", "/app/data/results"))
try:
    _results_dir.mkdir(parents=True, exist_ok=True)
except OSError:
    # Docker外（テストやローカル実行）で /app に書き込めない場合はローカルパスを使用
    _results_dir = Path(__file__).parent / "data" / "results"
    _results_dir.mkdir(parents=True, exist_ok=True)

result_store = ResultStore(results_dir=_results_dir)

# 排他制御用ロックと実行状態
_run_lock = threading.Lock()
_current_run: Optional[Dict[str, Any]] = None


def create_app() -> Flask:
    """Flaskアプリケーションを生成する"""
    app = Flask(__name__)

    @app.route("/health", methods=["GET"])
    def health():
        """ヘルスチェックエンドポイント

        Chrome(ChromeDriver)の状態、ターゲットURL、稼働時間を返す。
        """
        config = load_config_from_env()
        chrome_status = _check_chrome_status()
        uptime_seconds = time.time() - APP_START_TIME

        status = "healthy" if chrome_status == "ready" else "degraded"

        return jsonify({
            "status": status,
            "chrome_status": chrome_status,
            "target_app_url": config.target_app_url,
            "uptime_seconds": round(uptime_seconds, 1),
        })

    @app.route("/api/tests/run", methods=["POST"])
    def run_tests():
        """テスト実行開始エンドポイント

        全シナリオまたは指定シナリオのテストをバックグラウンドで実行開始する。
        既にテストが実行中の場合は409 Conflictを返す。
        """
        global _current_run

        # 排他制御: 既に実行中なら409
        with _run_lock:
            if _current_run is not None and _current_run.get("status") == "running":
                logger.warning("Test run rejected: another run is already in progress.")
                return jsonify({
                    "error": "A test run is already in progress",
                    "current_run_id": _current_run["run_id"],
                }), 409

            # リクエストボディの解析
            body = request.get_json(silent=True) or {}
            scenarios = body.get("scenarios", AVAILABLE_SCENARIOS)
            config_override = body.get("config", {})

            # 無効なシナリオ名のバリデーション
            invalid_scenarios = [s for s in scenarios if s not in AVAILABLE_SCENARIOS]
            if invalid_scenarios:
                return jsonify({
                    "error": f"Invalid scenarios: {invalid_scenarios}",
                    "available_scenarios": AVAILABLE_SCENARIOS,
                }), 400

            # 実行IDとランの生成
            run_id = str(uuid.uuid4())
            started_at = datetime.now(timezone.utc)

            _current_run = {
                "run_id": run_id,
                "status": "running",
                "started_at": started_at.isoformat(),
                "scenarios": scenarios,
                "progress": {
                    "total_scenarios": len(scenarios),
                    "completed_scenarios": 0,
                    "current_scenario": scenarios[0] if scenarios else None,
                },
            }

        # バックグラウンドスレッドでシナリオ実行開始
        thread = threading.Thread(
            target=_execute_run,
            args=(run_id, scenarios, config_override),
            daemon=True,
        )
        thread.start()

        logger.info(f"Test run started: run_id={run_id}, scenarios={scenarios}")

        return jsonify({
            "run_id": run_id,
            "status": "running",
            "started_at": started_at.isoformat(),
        }), 202

    @app.route("/api/tests/status/<run_id>", methods=["GET"])
    def get_status(run_id: str):
        """テスト実行ステータス取得エンドポイント"""
        global _current_run

        # 現在実行中のrunと一致するか確認
        if _current_run is not None and _current_run["run_id"] == run_id:
            return jsonify({
                "run_id": _current_run["run_id"],
                "status": _current_run["status"],
                "progress": _current_run["progress"],
                "started_at": _current_run["started_at"],
                "completed_at": _current_run.get("completed_at"),
            })

        # 完了済みの結果から検索
        result = result_store.get(run_id)
        if result is None:
            return jsonify({"error": f"Run ID '{run_id}' not found"}), 404

        return jsonify({
            "run_id": result.run_id,
            "status": result.status.value,
            "progress": {
                "total_scenarios": len(result.scenarios),
                "completed_scenarios": len(result.scenarios),
                "current_scenario": None,
            },
            "started_at": result.started_at.isoformat() if result.started_at else None,
            "completed_at": result.completed_at.isoformat() if result.completed_at else None,
        })

    @app.route("/api/tests/results/<run_id>", methods=["GET"])
    def get_results(run_id: str):
        """テスト実行結果取得エンドポイント

        完了した実行結果の詳細（RunResult.to_json()形式）を返す。
        """
        # 現在実行中の場合
        if _current_run is not None and _current_run["run_id"] == run_id:
            if _current_run["status"] == "running":
                return jsonify({
                    "error": "Test run is still in progress",
                    "run_id": run_id,
                    "status": "running",
                }), 409

        result = result_store.get(run_id)
        if result is None:
            return jsonify({"error": f"Run ID '{run_id}' not found"}), 404

        return jsonify(result.to_json())

    @app.route("/api/tests/history", methods=["GET"])
    def get_history():
        """テスト実行履歴取得エンドポイント（最新10件）"""
        history = result_store.get_history(limit=10)
        return jsonify({"history": history, "count": len(history)})

    return app


def _check_chrome_status() -> str:
    """ChromeDriverのステータスを確認する

    localhost:4444 のChromeDriverステータスエンドポイントに接続を試みる。

    Returns:
        "ready" (Chrome準備完了), "not_ready" (起動中), "unavailable" (接続不可)
    """
    try:
        resp = http_requests.get("http://localhost:4444/wd/hub/status", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("value", {}).get("ready", False):
                return "ready"
            return "not_ready"
        return "not_ready"
    except Exception:
        return "unavailable"


def _execute_run(run_id: str, scenarios: list, config_override: dict) -> None:
    """バックグラウンドスレッドでテストシナリオを実行する

    Args:
        run_id: 実行ID
        scenarios: 実行するシナリオ名のリスト
        config_override: リクエストで指定された設定オーバーライド
    """
    global _current_run

    try:
        # 設定の構築: 環境変数ベース + リクエストオーバーライド
        config = load_config_from_env()
        if "page_wait_seconds" in config_override:
            try:
                val = float(config_override["page_wait_seconds"])
                if val > 0:
                    config.page_wait_seconds = val
            except (ValueError, TypeError):
                pass
        if "browser_width" in config_override:
            try:
                val = int(config_override["browser_width"])
                if val > 0:
                    config.browser_width = val
            except (ValueError, TypeError):
                pass
        if "browser_height" in config_override:
            try:
                val = int(config_override["browser_height"])
                if val > 0:
                    config.browser_height = val
            except (ValueError, TypeError):
                pass

        logger.info(
            f"Executing test run {run_id} with config: "
            f"target={config.target_app_url}, "
            f"wait={config.page_wait_seconds}s, "
            f"window={config.browser_width}x{config.browser_height}"
        )

        # シナリオエンジンで実行
        engine = ScenarioEngine(config)
        run_result = engine.run_scenarios(scenarios)

        # run_idをAPIで発行したものに上書き
        run_result.run_id = run_id

        # 結果を保存
        result_store.save(run_result)

        # 実行状態を更新
        with _run_lock:
            _current_run = {
                "run_id": run_id,
                "status": run_result.status.value,
                "started_at": run_result.started_at.isoformat() if run_result.started_at else None,
                "completed_at": run_result.completed_at.isoformat() if run_result.completed_at else None,
                "scenarios": scenarios,
                "progress": {
                    "total_scenarios": len(scenarios),
                    "completed_scenarios": len(run_result.scenarios),
                    "current_scenario": None,
                },
            }

        logger.info(
            f"Test run {run_id} completed: status={run_result.status.value}, "
            f"summary={run_result.summary}"
        )

    except Exception as e:
        logger.error(f"Test run {run_id} failed with exception: {e}")
        with _run_lock:
            _current_run = {
                "run_id": run_id,
                "status": "failed",
                "started_at": _current_run.get("started_at") if _current_run else None,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "scenarios": scenarios,
                "progress": {
                    "total_scenarios": len(scenarios),
                    "completed_scenarios": 0,
                    "current_scenario": None,
                },
            }


# Flaskアプリのインスタンス生成（FLASK_APP=api で使用）
app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081)
