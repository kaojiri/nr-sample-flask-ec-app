"""Browser Test Runner API ユニットテスト

api.py の各エンドポイントのリクエスト/レスポンス形式、
排他制御、バリデーションをテストする。
"""

import json
import threading
import time
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest

from api import create_app, result_store, _run_lock, AVAILABLE_SCENARIOS
import api as api_module
from models import RunResult, TestStatus, ScenarioResult


@pytest.fixture
def app():
    """テスト用Flaskアプリケーション"""
    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    """テスト用クライアント"""
    return app.test_client()


@pytest.fixture(autouse=True)
def reset_state():
    """各テストの前にグローバル状態をリセット"""
    api_module._current_run = None
    result_store.recent_results.clear()
    # ファイルベースの結果もクリア
    for f in result_store.results_dir.glob("*.json"):
        f.unlink()
    yield
    api_module._current_run = None
    result_store.recent_results.clear()
    for f in result_store.results_dir.glob("*.json"):
        f.unlink()


class TestHealthEndpoint:
    """GET /health エンドポイントのテスト"""

    @patch("api._check_chrome_status", return_value="ready")
    @patch("api.load_config_from_env")
    def test_health_returns_healthy_when_chrome_ready(self, mock_config, mock_chrome, client):
        """Chromeが準備完了の場合、statusがhealthyを返す"""
        from models import RunnerConfig
        mock_config.return_value = RunnerConfig(target_app_url="http://web:5000")

        response = client.get("/health")
        data = response.get_json()

        assert response.status_code == 200
        assert data["status"] == "healthy"
        assert data["chrome_status"] == "ready"
        assert data["target_app_url"] == "http://web:5000"
        assert "uptime_seconds" in data
        assert isinstance(data["uptime_seconds"], float)

    @patch("api._check_chrome_status", return_value="unavailable")
    @patch("api.load_config_from_env")
    def test_health_returns_degraded_when_chrome_unavailable(self, mock_config, mock_chrome, client):
        """Chromeが利用不可の場合、statusがdegradedを返す"""
        from models import RunnerConfig
        mock_config.return_value = RunnerConfig()

        response = client.get("/health")
        data = response.get_json()

        assert response.status_code == 200
        assert data["status"] == "degraded"
        assert data["chrome_status"] == "unavailable"


class TestRunTestsEndpoint:
    """POST /api/tests/run エンドポイントのテスト"""

    @patch("api._execute_run")
    def test_run_returns_202_with_run_id(self, mock_execute, client):
        """テスト実行開始で202と実行情報を返す"""
        response = client.post(
            "/api/tests/run",
            json={"scenarios": ["navigation"]},
            content_type="application/json",
        )
        data = response.get_json()

        assert response.status_code == 202
        assert "run_id" in data
        assert data["status"] == "running"
        assert "started_at" in data

    @patch("api._execute_run")
    def test_run_default_scenarios_when_none_specified(self, mock_execute, client):
        """シナリオ未指定の場合は全シナリオを実行"""
        response = client.post(
            "/api/tests/run",
            json={},
            content_type="application/json",
        )

        assert response.status_code == 202
        # _execute_runに全シナリオが渡されることを確認
        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        assert call_args[1] == AVAILABLE_SCENARIOS

    @patch("api._execute_run")
    def test_run_with_specific_scenarios(self, mock_execute, client):
        """指定シナリオのみ実行"""
        response = client.post(
            "/api/tests/run",
            json={"scenarios": ["navigation", "ajax"]},
            content_type="application/json",
        )

        assert response.status_code == 202
        call_args = mock_execute.call_args[0]
        assert call_args[1] == ["navigation", "ajax"]

    @patch("api._execute_run")
    def test_run_returns_400_for_invalid_scenarios(self, mock_execute, client):
        """無効なシナリオ名で400を返す"""
        response = client.post(
            "/api/tests/run",
            json={"scenarios": ["nonexistent"]},
            content_type="application/json",
        )
        data = response.get_json()

        assert response.status_code == 400
        assert "error" in data
        assert "available_scenarios" in data
        mock_execute.assert_not_called()

    @patch("api._execute_run")
    def test_run_returns_409_when_already_running(self, mock_execute, client):
        """既に実行中の場合は409 Conflictを返す"""
        # 最初の実行を開始
        api_module._current_run = {
            "run_id": "existing-run-id",
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "scenarios": ["navigation"],
            "progress": {
                "total_scenarios": 1,
                "completed_scenarios": 0,
                "current_scenario": "navigation",
            },
        }

        response = client.post(
            "/api/tests/run",
            json={"scenarios": ["navigation"]},
            content_type="application/json",
        )
        data = response.get_json()

        assert response.status_code == 409
        assert "error" in data
        assert data["current_run_id"] == "existing-run-id"

    @patch("api._execute_run")
    def test_run_allows_new_run_after_completed(self, mock_execute, client):
        """完了済みの場合は新しい実行を許可する"""
        api_module._current_run = {
            "run_id": "completed-run-id",
            "status": "completed",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "scenarios": ["navigation"],
            "progress": {
                "total_scenarios": 1,
                "completed_scenarios": 1,
                "current_scenario": None,
            },
        }

        response = client.post(
            "/api/tests/run",
            json={"scenarios": ["navigation"]},
            content_type="application/json",
        )

        assert response.status_code == 202

    @patch("api._execute_run")
    def test_run_with_config_override(self, mock_execute, client):
        """config指定が_execute_runに渡される"""
        response = client.post(
            "/api/tests/run",
            json={
                "scenarios": ["navigation"],
                "config": {
                    "page_wait_seconds": 5,
                    "browser_width": 1280,
                    "browser_height": 720,
                },
            },
            content_type="application/json",
        )

        assert response.status_code == 202
        call_args = mock_execute.call_args[0]
        config_override = call_args[2]
        assert config_override["page_wait_seconds"] == 5
        assert config_override["browser_width"] == 1280

    @patch("api._execute_run")
    def test_run_with_empty_body(self, mock_execute, client):
        """空のリクエストボディでもデフォルトシナリオで実行"""
        response = client.post("/api/tests/run")

        assert response.status_code == 202


class TestStatusEndpoint:
    """GET /api/tests/status/{run_id} エンドポイントのテスト"""

    def test_status_returns_current_run_info(self, client):
        """実行中のrunの場合、進捗情報を返す"""
        api_module._current_run = {
            "run_id": "test-run-123",
            "status": "running",
            "started_at": "2024-01-01T00:00:00+00:00",
            "completed_at": None,
            "scenarios": ["navigation", "ajax"],
            "progress": {
                "total_scenarios": 2,
                "completed_scenarios": 1,
                "current_scenario": "ajax",
            },
        }

        response = client.get("/api/tests/status/test-run-123")
        data = response.get_json()

        assert response.status_code == 200
        assert data["run_id"] == "test-run-123"
        assert data["status"] == "running"
        assert data["progress"]["total_scenarios"] == 2
        assert data["progress"]["completed_scenarios"] == 1
        assert data["progress"]["current_scenario"] == "ajax"

    def test_status_returns_completed_run_from_store(self, client):
        """完了済みrunの場合、result_storeから返す"""
        run_result = RunResult(
            run_id="completed-run",
            status=TestStatus.COMPLETED,
            started_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            completed_at=datetime(2024, 1, 1, 0, 2, 0, tzinfo=timezone.utc),
            scenarios=[
                ScenarioResult(name="navigation", status=TestStatus.COMPLETED),
            ],
        )
        result_store.save(run_result)

        response = client.get("/api/tests/status/completed-run")
        data = response.get_json()

        assert response.status_code == 200
        assert data["run_id"] == "completed-run"
        assert data["status"] == "completed"
        assert data["progress"]["total_scenarios"] == 1
        assert data["progress"]["completed_scenarios"] == 1

    def test_status_returns_404_for_unknown_run(self, client):
        """存在しないrun_idの場合は404を返す"""
        response = client.get("/api/tests/status/nonexistent-id")
        data = response.get_json()

        assert response.status_code == 404
        assert "error" in data


class TestResultsEndpoint:
    """GET /api/tests/results/{run_id} エンドポイントのテスト"""

    def test_results_returns_full_run_result(self, client):
        """完了した実行結果のJSON全体を返す"""
        run_result = RunResult(
            run_id="result-run-1",
            status=TestStatus.COMPLETED,
            started_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            completed_at=datetime(2024, 1, 1, 0, 1, 0, tzinfo=timezone.utc),
            scenarios=[
                ScenarioResult(
                    name="navigation",
                    status=TestStatus.COMPLETED,
                    duration_seconds=30.0,
                    expected_events={"PageView": 6},
                ),
            ],
        )
        result_store.save(run_result)

        response = client.get("/api/tests/results/result-run-1")
        data = response.get_json()

        assert response.status_code == 200
        assert data["run_id"] == "result-run-1"
        assert data["status"] == "completed"
        assert "summary" in data
        assert "scenarios" in data
        assert data["scenarios"][0]["name"] == "navigation"
        assert data["expected_newrelic_events"]["PageView"] == 6

    def test_results_returns_409_when_still_running(self, client):
        """まだ実行中のrun_idの場合は409を返す"""
        api_module._current_run = {
            "run_id": "running-run-id",
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "scenarios": ["navigation"],
            "progress": {
                "total_scenarios": 1,
                "completed_scenarios": 0,
                "current_scenario": "navigation",
            },
        }

        response = client.get("/api/tests/results/running-run-id")
        data = response.get_json()

        assert response.status_code == 409
        assert data["status"] == "running"

    def test_results_returns_404_for_unknown_run(self, client):
        """存在しないrun_idの場合は404を返す"""
        response = client.get("/api/tests/results/nonexistent-id")

        assert response.status_code == 404


class TestHistoryEndpoint:
    """GET /api/tests/history エンドポイントのテスト"""

    def test_history_returns_empty_list_initially(self, client):
        """初期状態では空リストを返す"""
        response = client.get("/api/tests/history")
        data = response.get_json()

        assert response.status_code == 200
        assert data["history"] == []
        assert data["count"] == 0

    def test_history_returns_stored_results(self, client):
        """保存された結果をリストで返す"""
        for i in range(3):
            run_result = RunResult(
                run_id=f"history-run-{i}",
                status=TestStatus.COMPLETED,
                started_at=datetime(2024, 1, 1, i, 0, 0, tzinfo=timezone.utc),
                completed_at=datetime(2024, 1, 1, i, 1, 0, tzinfo=timezone.utc),
            )
            result_store.save(run_result)

        response = client.get("/api/tests/history")
        data = response.get_json()

        assert response.status_code == 200
        assert data["count"] == 3
        assert len(data["history"]) == 3


class TestExclusiveExecution:
    """排他制御のテスト"""

    @patch("api._execute_run")
    def test_concurrent_requests_blocked(self, mock_execute, client):
        """同時に2つの実行リクエストが来た場合、2つ目は409を返す"""
        # 1つ目を開始
        response1 = client.post(
            "/api/tests/run",
            json={"scenarios": ["navigation"]},
            content_type="application/json",
        )
        assert response1.status_code == 202

        # 2つ目は拒否される
        response2 = client.post(
            "/api/tests/run",
            json={"scenarios": ["ajax"]},
            content_type="application/json",
        )
        assert response2.status_code == 409


class TestCheckChromeStatus:
    """_check_chrome_status関数のテスト"""

    @patch("api.http_requests.get")
    def test_returns_ready_when_chrome_is_ready(self, mock_get):
        """ChromeDriverが準備完了の場合'ready'を返す"""
        from api import _check_chrome_status

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"value": {"ready": True}}
        mock_get.return_value = mock_response

        assert _check_chrome_status() == "ready"

    @patch("api.http_requests.get")
    def test_returns_not_ready_when_chrome_not_ready(self, mock_get):
        """ChromeDriverが起動中の場合'not_ready'を返す"""
        from api import _check_chrome_status

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"value": {"ready": False}}
        mock_get.return_value = mock_response

        assert _check_chrome_status() == "not_ready"

    @patch("api.http_requests.get")
    def test_returns_unavailable_on_connection_error(self, mock_get):
        """接続エラーの場合'unavailable'を返す"""
        from api import _check_chrome_status

        mock_get.side_effect = Exception("Connection refused")

        assert _check_chrome_status() == "unavailable"


class TestExecuteRun:
    """_execute_run関数のテスト"""

    @patch("api.ScenarioEngine")
    @patch("api.load_config_from_env")
    def test_execute_run_saves_result(self, mock_config, mock_engine_cls):
        """実行完了後にresult_storeに結果が保存される"""
        from api import _execute_run
        from models import RunnerConfig

        mock_config.return_value = RunnerConfig()

        mock_engine = MagicMock()
        mock_run_result = RunResult(
            run_id="temp-id",
            status=TestStatus.COMPLETED,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        mock_engine.run_scenarios.return_value = mock_run_result
        mock_engine_cls.return_value = mock_engine

        api_module._current_run = {
            "run_id": "exec-run-1",
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "scenarios": ["navigation"],
            "progress": {
                "total_scenarios": 1,
                "completed_scenarios": 0,
                "current_scenario": "navigation",
            },
        }

        _execute_run("exec-run-1", ["navigation"], {})

        # 結果がストアに保存されている
        saved = result_store.get("exec-run-1")
        assert saved is not None
        assert saved.run_id == "exec-run-1"

    @patch("api.ScenarioEngine")
    @patch("api.load_config_from_env")
    def test_execute_run_applies_config_override(self, mock_config, mock_engine_cls):
        """configオーバーライドが適用される"""
        from api import _execute_run
        from models import RunnerConfig

        config = RunnerConfig()
        mock_config.return_value = config

        mock_engine = MagicMock()
        mock_engine.run_scenarios.return_value = RunResult(
            status=TestStatus.COMPLETED,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        mock_engine_cls.return_value = mock_engine

        api_module._current_run = {
            "run_id": "config-run",
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "scenarios": ["navigation"],
            "progress": {
                "total_scenarios": 1,
                "completed_scenarios": 0,
                "current_scenario": "navigation",
            },
        }

        _execute_run("config-run", ["navigation"], {
            "page_wait_seconds": 5,
            "browser_width": 1280,
            "browser_height": 720,
        })

        # ScenarioEngineに渡された設定を確認
        engine_config = mock_engine_cls.call_args[0][0]
        assert engine_config.page_wait_seconds == 5
        assert engine_config.browser_width == 1280
        assert engine_config.browser_height == 720

    @patch("api.ScenarioEngine")
    @patch("api.load_config_from_env")
    def test_execute_run_handles_exception(self, mock_config, mock_engine_cls):
        """実行中の例外がcatchされてstatus=failedになる"""
        from api import _execute_run
        from models import RunnerConfig

        mock_config.return_value = RunnerConfig()
        mock_engine_cls.side_effect = Exception("Engine failed")

        api_module._current_run = {
            "run_id": "fail-run",
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "scenarios": ["navigation"],
            "progress": {
                "total_scenarios": 1,
                "completed_scenarios": 0,
                "current_scenario": "navigation",
            },
        }

        _execute_run("fail-run", ["navigation"], {})

        # _current_runがfailedに更新されている
        assert api_module._current_run["status"] == "failed"
