"""
ブラウザテスト管理ダッシュボード ルート
Browser Test Runner APIへのプロキシエンドポイントとダッシュボード表示
"""

from flask import Blueprint, render_template, request, jsonify, current_app
import requests
import os
import logging

logger = logging.getLogger(__name__)

# Blueprintの作成
bp = Blueprint('browser_tests', __name__, url_prefix='/browser-tests')

# Browser Test Runner APIのベースURL
BROWSER_TESTER_URL = os.environ.get("BROWSER_TESTER_URL", "http://browser-tester:8081")


def get_runner_status():
    """Browser Test Runnerの接続状態を確認"""
    try:
        response = requests.get(f"{BROWSER_TESTER_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return {
                "connected": True,
                "status": data.get("status", "unknown"),
                "chrome_status": data.get("chrome_status", "unknown"),
                "target_app_url": data.get("target_app_url", "unknown"),
                "uptime_seconds": data.get("uptime_seconds", 0),
            }
        else:
            return {
                "connected": False,
                "status": "error",
                "error": f"HTTP {response.status_code}",
            }
    except requests.ConnectionError:
        return {
            "connected": False,
            "status": "disconnected",
            "error": "Browser Test Runnerに接続できません",
        }
    except requests.Timeout:
        return {
            "connected": False,
            "status": "timeout",
            "error": "接続がタイムアウトしました",
        }
    except Exception as e:
        return {
            "connected": False,
            "status": "error",
            "error": str(e),
        }


def get_test_history():
    """テスト実行履歴を取得"""
    try:
        response = requests.get(
            f"{BROWSER_TESTER_URL}/api/tests/history", timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            # APIは {"history": [...], "count": N} を返す
            if isinstance(data, dict):
                return data.get("history", [])
            return data if isinstance(data, list) else []
        return []
    except (requests.ConnectionError, requests.Timeout, Exception):
        return []


@bp.route('/')
def dashboard():
    """テスト管理ダッシュボードページ"""
    runner_status = get_runner_status()
    test_history = get_test_history()
    return render_template(
        'browser_tests/dashboard.html',
        runner_status=runner_status,
        test_history=test_history,
    )


@bp.route('/api/run', methods=['POST'])
def trigger_run():
    """テスト実行をBrowser Test Runnerに委譲"""
    try:
        scenarios = request.json.get('scenarios') if request.json else None
        payload = {}
        if scenarios:
            payload["scenarios"] = scenarios

        response = requests.post(
            f"{BROWSER_TESTER_URL}/api/tests/run",
            json=payload,
            timeout=10,
        )
        return jsonify(response.json()), response.status_code
    except requests.ConnectionError:
        return jsonify({
            "error": "Browser Test Runnerに接続できません",
            "status": "connection_error",
        }), 503
    except requests.Timeout:
        return jsonify({
            "error": "Browser Test Runnerへの接続がタイムアウトしました",
            "status": "timeout",
        }), 504
    except Exception as e:
        logger.error(f"Error triggering test run: {e}")
        return jsonify({
            "error": "テスト実行のトリガーに失敗しました",
            "details": str(e),
        }), 500


@bp.route('/api/status/<run_id>')
def get_status(run_id):
    """実行ステータスをプロキシ取得"""
    try:
        response = requests.get(
            f"{BROWSER_TESTER_URL}/api/tests/status/{run_id}",
            timeout=5,
        )
        return jsonify(response.json()), response.status_code
    except requests.ConnectionError:
        return jsonify({
            "error": "Browser Test Runnerに接続できません",
            "status": "connection_error",
        }), 503
    except requests.Timeout:
        return jsonify({
            "error": "接続がタイムアウトしました",
            "status": "timeout",
        }), 504
    except Exception as e:
        logger.error(f"Error getting status for run {run_id}: {e}")
        return jsonify({
            "error": "ステータス取得に失敗しました",
            "details": str(e),
        }), 500


@bp.route('/api/results/<run_id>')
def get_results(run_id):
    """実行結果をプロキシ取得"""
    try:
        response = requests.get(
            f"{BROWSER_TESTER_URL}/api/tests/results/{run_id}",
            timeout=10,
        )
        return jsonify(response.json()), response.status_code
    except requests.ConnectionError:
        return jsonify({
            "error": "Browser Test Runnerに接続できません",
            "status": "connection_error",
        }), 503
    except requests.Timeout:
        return jsonify({
            "error": "接続がタイムアウトしました",
            "status": "timeout",
        }), 504
    except Exception as e:
        logger.error(f"Error getting results for run {run_id}: {e}")
        return jsonify({
            "error": "結果取得に失敗しました",
            "details": str(e),
        }), 500
