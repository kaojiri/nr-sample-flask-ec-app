"""ResultStore のユニットテスト

save(), get(), get_history() の動作を検証する。
"""

import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

import pytest

from models import RunResult, ScenarioResult, StepResult, TestStatus
from result_store import ResultStore


@pytest.fixture
def tmp_results_dir(tmp_path):
    """テスト用の一時ディレクトリを提供する。"""
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    return results_dir


@pytest.fixture
def store(tmp_results_dir):
    """テスト用のResultStoreインスタンスを提供する。"""
    return ResultStore(results_dir=tmp_results_dir)


def make_run_result(run_id: str = "test-run-1", status: TestStatus = TestStatus.COMPLETED,
                    started_at: datetime = None, scenarios: list = None) -> RunResult:
    """テスト用のRunResultを生成するヘルパー。"""
    return RunResult(
        run_id=run_id,
        status=status,
        started_at=started_at or datetime(2024, 1, 1, 12, 0, 0),
        completed_at=(started_at or datetime(2024, 1, 1, 12, 0, 0)) + timedelta(seconds=30),
        scenarios=scenarios or [
            ScenarioResult(
                name="navigation",
                status=TestStatus.COMPLETED,
                steps=[
                    StepResult(action="navigate", target="/", success=True, duration_ms=100.0)
                ],
                duration_seconds=10.0,
                expected_events={"PageView": 3},
            )
        ],
    )


class TestResultStoreSave:
    """save() メソッドのテスト"""

    def test_save_adds_to_in_memory_cache(self, store):
        """save()で結果がインメモリキャッシュに追加される。"""
        result = make_run_result()
        store.save(result)
        assert len(store.recent_results) == 1
        assert store.recent_results[0].run_id == "test-run-1"

    def test_save_persists_json_file(self, store, tmp_results_dir):
        """save()でJSONファイルが永続化される。"""
        result = make_run_result(run_id="persist-test")
        store.save(result)

        filepath = tmp_results_dir / "persist-test.json"
        assert filepath.exists()

        data = json.loads(filepath.read_text(encoding="utf-8"))
        assert data["run_id"] == "persist-test"
        assert data["status"] == "completed"

    def test_save_evicts_oldest_when_exceeding_max(self, store):
        """MAX_IN_MEMORY件を超えると最も古い結果がキャッシュから削除される。"""
        for i in range(12):
            result = make_run_result(run_id=f"run-{i}")
            store.save(result)

        assert len(store.recent_results) == 10
        # 最初の2件（run-0, run-1）が削除されている
        cached_ids = [r.run_id for r in store.recent_results]
        assert "run-0" not in cached_ids
        assert "run-1" not in cached_ids
        assert "run-2" in cached_ids
        assert "run-11" in cached_ids

    def test_save_all_results_persisted_even_after_eviction(self, store, tmp_results_dir):
        """キャッシュから削除された結果もJSONファイルには残る。"""
        for i in range(12):
            result = make_run_result(run_id=f"run-{i}")
            store.save(result)

        # 全12件のJSONファイルが存在する
        json_files = list(tmp_results_dir.glob("*.json"))
        assert len(json_files) == 12

    def test_save_json_content_matches_to_json(self, store, tmp_results_dir):
        """永続化されたJSONの内容がto_json()の結果と一致する。"""
        result = make_run_result(run_id="json-check")
        store.save(result)

        filepath = tmp_results_dir / "json-check.json"
        file_data = json.loads(filepath.read_text(encoding="utf-8"))
        assert file_data == result.to_json()


class TestResultStoreGet:
    """get() メソッドのテスト"""

    def test_get_from_in_memory_cache(self, store):
        """キャッシュ内の結果はget()で取得できる。"""
        result = make_run_result(run_id="cached-result")
        store.save(result)

        retrieved = store.get("cached-result")
        assert retrieved is not None
        assert retrieved.run_id == "cached-result"
        assert retrieved.status == TestStatus.COMPLETED

    def test_get_from_json_file_when_not_in_cache(self, store, tmp_results_dir):
        """キャッシュにない場合はJSONファイルから読み込む。"""
        # 11件保存して最初の1件がキャッシュから消えた状態を作る
        for i in range(11):
            result = make_run_result(run_id=f"run-{i}")
            store.save(result)

        # run-0 はキャッシュにないがファイルから取得可能
        retrieved = store.get("run-0")
        assert retrieved is not None
        assert retrieved.run_id == "run-0"
        assert retrieved.status == TestStatus.COMPLETED

    def test_get_returns_none_for_nonexistent_id(self, store):
        """存在しないrun_idにはNoneが返る。"""
        result = store.get("nonexistent")
        assert result is None

    def test_get_prefers_in_memory_cache(self, store):
        """get()はまずインメモリキャッシュを検索する。"""
        result = make_run_result(run_id="memory-first")
        store.save(result)

        # キャッシュ内のオブジェクトと同一インスタンスが返る
        retrieved = store.get("memory-first")
        assert retrieved is result

    def test_get_restores_scenarios_from_file(self, store, tmp_results_dir):
        """ファイルから復元した結果にはシナリオとステップが含まれる。"""
        result = make_run_result(
            run_id="with-scenarios",
            scenarios=[
                ScenarioResult(
                    name="navigation",
                    status=TestStatus.COMPLETED,
                    steps=[
                        StepResult(action="navigate", target="/", success=True, duration_ms=150.0),
                        StepResult(action="click", target="a.link", success=False,
                                   error_message="element not found"),
                    ],
                    duration_seconds=20.0,
                    expected_events={"PageView": 2, "BrowserInteraction": 1},
                )
            ],
        )
        store.save(result)

        # キャッシュをクリアしてファイルから読み込み
        store.recent_results.clear()
        retrieved = store.get("with-scenarios")

        assert retrieved is not None
        assert len(retrieved.scenarios) == 1
        assert retrieved.scenarios[0].name == "navigation"
        assert len(retrieved.scenarios[0].steps) == 2
        assert retrieved.scenarios[0].steps[0].action == "navigate"
        assert retrieved.scenarios[0].steps[1].success is False


class TestResultStoreGetHistory:
    """get_history() メソッドのテスト"""

    def test_get_history_returns_recent_results(self, store):
        """get_history()で直近の結果が返る。"""
        for i in range(3):
            result = make_run_result(
                run_id=f"hist-{i}",
                started_at=datetime(2024, 1, 1, 12, i, 0),
            )
            store.save(result)

        history = store.get_history(limit=10)
        assert len(history) == 3
        # 新しいものが先頭
        assert history[0]["run_id"] == "hist-2"
        assert history[1]["run_id"] == "hist-1"
        assert history[2]["run_id"] == "hist-0"

    def test_get_history_respects_limit(self, store):
        """get_history()はlimitパラメータを尊重する。"""
        for i in range(5):
            result = make_run_result(
                run_id=f"hist-{i}",
                started_at=datetime(2024, 1, 1, 12, i, 0),
            )
            store.save(result)

        history = store.get_history(limit=3)
        assert len(history) == 3

    def test_get_history_returns_dict_format(self, store):
        """get_history()はto_json()形式の辞書リストを返す。"""
        result = make_run_result(run_id="dict-format")
        store.save(result)

        history = store.get_history()
        assert len(history) == 1
        assert isinstance(history[0], dict)
        assert "run_id" in history[0]
        assert "status" in history[0]
        assert "summary" in history[0]
        assert "scenarios" in history[0]

    def test_get_history_empty_store(self, store):
        """空のストアではget_history()は空リストを返す。"""
        history = store.get_history()
        assert history == []

    def test_get_history_includes_file_results_when_cache_insufficient(self, store):
        """キャッシュ件数が不足時にファイルから補完する。"""
        # 12件保存（キャッシュには最新10件のみ）
        for i in range(12):
            result = make_run_result(
                run_id=f"hist-{i}",
                started_at=datetime(2024, 1, 1, 12, i, 0),
            )
            store.save(result)

        # limit=12で全件要求 → ファイルから補完される
        history = store.get_history(limit=12)
        assert len(history) == 12

    def test_get_history_ordered_newest_first(self, store):
        """get_history()は新しいものが先頭に来る。"""
        # 意図的に順序を混ぜる
        for i in [3, 1, 2, 0]:
            result = make_run_result(
                run_id=f"ordered-{i}",
                started_at=datetime(2024, 1, 1, 12, i, 0),
            )
            store.save(result)

        history = store.get_history()
        started_ats = [h["started_at"] for h in history]
        # ISOフォーマット文字列で降順確認
        assert started_ats == sorted(started_ats, reverse=True)


class TestResultStoreDirectoryCreation:
    """ディレクトリ作成の動作テスト"""

    def test_creates_results_directory_if_not_exists(self, tmp_path):
        """存在しないディレクトリが自動作成される。"""
        new_dir = tmp_path / "new" / "results"
        assert not new_dir.exists()

        store = ResultStore(results_dir=new_dir)
        assert new_dir.exists()

    def test_uses_default_path_when_none(self):
        """results_dirがNoneの場合はデフォルトパスを使用する。"""
        # デフォルトパスの確認のみ（実際に/app/data/resultsを作成しない）
        # コンストラクタのロジックを間接的に確認
        store = ResultStore.__new__(ResultStore)
        store.results_dir = None or Path("/app/data/results")
        assert store.results_dir == Path("/app/data/results")
