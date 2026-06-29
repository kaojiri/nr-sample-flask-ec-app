"""データモデル定義: テスト実行結果と設定"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import uuid


class TestStatus(Enum):
    """テスト実行ステータス"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class StepResult:
    """個別操作ステップの結果"""
    action: str                    # "navigate", "click", "fill", "trigger_error"
    target: str                    # URL path or CSS selector
    success: bool
    duration_ms: float = 0.0
    error_message: Optional[str] = None
    page_name: Optional[str] = None
    verified: bool = True
    load_time_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScenarioResult:
    """シナリオ実行結果"""
    name: str
    status: TestStatus
    steps: List[StepResult] = field(default_factory=list)
    duration_seconds: float = 0.0
    error_message: Optional[str] = None
    retry_count: int = 0
    expected_events: Dict[str, int] = field(default_factory=dict)


@dataclass
class RunResult:
    """テスト実行全体の結果"""
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: TestStatus = TestStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    scenarios: List[ScenarioResult] = field(default_factory=list)
    config_used: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0

    @property
    def summary(self) -> Dict[str, int]:
        total = len(self.scenarios)
        passed = sum(1 for s in self.scenarios if s.status == TestStatus.COMPLETED)
        failed = sum(1 for s in self.scenarios if s.status == TestStatus.FAILED)
        return {"total": total, "passed": passed, "failed": failed}

    @property
    def expected_newrelic_events(self) -> Dict[str, int]:
        events: Dict[str, int] = {}
        for scenario in self.scenarios:
            for event_type, count in scenario.expected_events.items():
                events[event_type] = events.get(event_type, 0) + count
        return events

    def to_json(self) -> Dict[str, Any]:
        """JSON シリアライズ"""
        return {
            "run_id": self.run_id,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "summary": self.summary,
            "expected_newrelic_events": self.expected_newrelic_events,
            "scenarios": [
                {
                    "name": s.name,
                    "status": s.status.value,
                    "duration_seconds": s.duration_seconds,
                    "steps": [
                        {
                            "action": step.action,
                            "target": step.target,
                            "success": step.success,
                            "duration_ms": step.duration_ms,
                            "error_message": step.error_message,
                            "load_time_ms": step.load_time_ms,
                        }
                        for step in s.steps
                    ],
                    "expected_events": s.expected_events,
                    "error_message": s.error_message,
                }
                for s in self.scenarios
            ],
        }


@dataclass
class RunnerConfig:
    """テストランナー設定"""
    target_app_url: str = "http://web:5000"
    page_wait_seconds: float = 3.0
    browser_width: int = 1920
    browser_height: int = 1080
    retry_count: int = 1
    page_timeout_seconds: int = 10
    log_level: str = "INFO"
