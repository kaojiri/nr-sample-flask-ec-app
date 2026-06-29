"""models.py のユニットテスト"""

import json
from datetime import datetime
from models import TestStatus, StepResult, ScenarioResult, RunResult, RunnerConfig


class TestTestStatus:
    """TestStatus enum のテスト"""

    def test_all_values(self):
        assert TestStatus.PENDING.value == "pending"
        assert TestStatus.RUNNING.value == "running"
        assert TestStatus.COMPLETED.value == "completed"
        assert TestStatus.FAILED.value == "failed"
        assert TestStatus.CANCELLED.value == "cancelled"

    def test_enum_count(self):
        assert len(TestStatus) == 5


class TestStepResult:
    """StepResult dataclass のテスト"""

    def test_required_fields(self):
        step = StepResult(action="navigate", target="/", success=True)
        assert step.action == "navigate"
        assert step.target == "/"
        assert step.success is True

    def test_default_values(self):
        step = StepResult(action="click", target="button", success=False)
        assert step.duration_ms == 0.0
        assert step.error_message is None
        assert step.page_name is None
        assert step.verified is True
        assert step.load_time_ms is None
        assert step.metadata == {}

    def test_all_fields(self):
        step = StepResult(
            action="trigger_error",
            target="Null Reference",
            success=True,
            duration_ms=50.5,
            error_message=None,
            page_name="JS Errors",
            verified=True,
            load_time_ms=200.0,
            metadata={"console_errors": 3},
        )
        assert step.duration_ms == 50.5
        assert step.page_name == "JS Errors"
        assert step.load_time_ms == 200.0
        assert step.metadata == {"console_errors": 3}


class TestScenarioResult:
    """ScenarioResult dataclass のテスト"""

    def test_required_fields(self):
        result = ScenarioResult(name="navigation", status=TestStatus.COMPLETED)
        assert result.name == "navigation"
        assert result.status == TestStatus.COMPLETED

    def test_default_values(self):
        result = ScenarioResult(name="test", status=TestStatus.PENDING)
        assert result.steps == []
        assert result.duration_seconds == 0.0
        assert result.error_message is None
        assert result.retry_count == 0
        assert result.expected_events == {}

    def test_with_expected_events(self):
        result = ScenarioResult(
            name="navigation",
            status=TestStatus.COMPLETED,
            expected_events={"PageView": 6, "BrowserInteraction": 2},
        )
        assert result.expected_events["PageView"] == 6
        assert result.expected_events["BrowserInteraction"] == 2


class TestRunResult:
    """RunResult dataclass のテスト"""

    def test_default_values(self):
        run = RunResult()
        assert run.run_id  # UUID should be generated
        assert run.status == TestStatus.PENDING
        assert run.started_at is None
        assert run.completed_at is None
        assert run.scenarios == []
        assert run.config_used == {}

    def test_duration_seconds_with_times(self):
        run = RunResult(
            started_at=datetime(2024, 1, 1, 0, 0, 0),
            completed_at=datetime(2024, 1, 1, 0, 2, 30),
        )
        assert run.duration_seconds == 150.0

    def test_duration_seconds_without_times(self):
        run = RunResult()
        assert run.duration_seconds == 0.0

    def test_duration_seconds_partial_times(self):
        run = RunResult(started_at=datetime(2024, 1, 1, 0, 0, 0))
        assert run.duration_seconds == 0.0

    def test_summary_empty(self):
        run = RunResult()
        assert run.summary == {"total": 0, "passed": 0, "failed": 0}

    def test_summary_with_scenarios(self):
        scenarios = [
            ScenarioResult(name="s1", status=TestStatus.COMPLETED),
            ScenarioResult(name="s2", status=TestStatus.COMPLETED),
            ScenarioResult(name="s3", status=TestStatus.FAILED),
            ScenarioResult(name="s4", status=TestStatus.RUNNING),
        ]
        run = RunResult(scenarios=scenarios)
        assert run.summary == {"total": 4, "passed": 2, "failed": 1}

    def test_expected_newrelic_events_empty(self):
        run = RunResult()
        assert run.expected_newrelic_events == {}

    def test_expected_newrelic_events_aggregation(self):
        scenarios = [
            ScenarioResult(
                name="nav",
                status=TestStatus.COMPLETED,
                expected_events={"PageView": 6},
            ),
            ScenarioResult(
                name="interaction",
                status=TestStatus.COMPLETED,
                expected_events={"BrowserInteraction": 4, "PageView": 2},
            ),
            ScenarioResult(
                name="js_errors",
                status=TestStatus.FAILED,
                expected_events={"JavaScriptError": 6},
            ),
        ]
        run = RunResult(scenarios=scenarios)
        expected = {"PageView": 8, "BrowserInteraction": 4, "JavaScriptError": 6}
        assert run.expected_newrelic_events == expected

    def test_to_json_required_fields(self):
        run = RunResult()
        result = run.to_json()
        assert "run_id" in result
        assert "status" in result
        assert "started_at" in result
        assert "completed_at" in result
        assert "duration_seconds" in result
        assert "summary" in result
        assert "expected_newrelic_events" in result
        assert "scenarios" in result

    def test_to_json_serializable(self):
        run = RunResult(
            status=TestStatus.COMPLETED,
            started_at=datetime(2024, 1, 1, 12, 0, 0),
            completed_at=datetime(2024, 1, 1, 12, 5, 0),
            scenarios=[
                ScenarioResult(
                    name="nav",
                    status=TestStatus.COMPLETED,
                    steps=[
                        StepResult(
                            action="navigate",
                            target="/",
                            success=True,
                            duration_ms=100.0,
                            load_time_ms=80.0,
                        )
                    ],
                    expected_events={"PageView": 1},
                )
            ],
        )
        result = run.to_json()
        # Must be JSON-serializable without exceptions
        json_str = json.dumps(result)
        assert isinstance(json_str, str)
        # Verify round-trip
        parsed = json.loads(json_str)
        assert parsed["status"] == "completed"
        assert parsed["scenarios"][0]["name"] == "nav"

    def test_to_json_none_timestamps(self):
        run = RunResult()
        result = run.to_json()
        assert result["started_at"] is None
        assert result["completed_at"] is None

    def test_to_json_status_as_string(self):
        run = RunResult(status=TestStatus.RUNNING)
        result = run.to_json()
        assert result["status"] == "running"

    def test_unique_run_ids(self):
        run1 = RunResult()
        run2 = RunResult()
        assert run1.run_id != run2.run_id


class TestRunnerConfig:
    """RunnerConfig dataclass のテスト"""

    def test_default_values(self):
        config = RunnerConfig()
        assert config.target_app_url == "http://web:5000"
        assert config.page_wait_seconds == 3.0
        assert config.browser_width == 1920
        assert config.browser_height == 1080
        assert config.retry_count == 1
        assert config.page_timeout_seconds == 10
        assert config.log_level == "INFO"

    def test_custom_values(self):
        config = RunnerConfig(
            target_app_url="http://localhost:5001",
            page_wait_seconds=5.0,
            browser_width=1280,
            browser_height=720,
            retry_count=3,
            page_timeout_seconds=30,
            log_level="DEBUG",
        )
        assert config.target_app_url == "http://localhost:5001"
        assert config.page_wait_seconds == 5.0
        assert config.browser_width == 1280
        assert config.browser_height == 720
        assert config.retry_count == 3
        assert config.page_timeout_seconds == 30
        assert config.log_level == "DEBUG"
