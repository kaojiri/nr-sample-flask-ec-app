"""テスト結果の保存・取得

インメモリ（直近10件）+ JSONファイル永続化でテスト結果を管理する。
"""

import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from models import RunResult, TestStatus, ScenarioResult, StepResult


class ResultStore:
    """テスト結果の保存・取得
    
    インメモリキャッシュ（直近MAX_IN_MEMORY件）とJSONファイル永続化の
    2層構造で結果を管理する。
    """

    MAX_IN_MEMORY = 10

    def __init__(self, results_dir: Optional[Path] = None):
        """ResultStoreを初期化する。
        
        Args:
            results_dir: 結果JSONファイルの保存先ディレクトリ。
                         Noneの場合は /app/data/results/ を使用する。
        """
        self.results_dir = results_dir or Path("/app/data/results")
        self.recent_results: List[RunResult] = []
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def save(self, result: RunResult) -> None:
        """結果を保存する。
        
        インメモリキャッシュに追加し（MAX_IN_MEMORY件を超えたら古いものを削除）、
        同時にJSONファイルとしても永続化する。
        
        Args:
            result: 保存するRunResultオブジェクト
        """
        self.recent_results.append(result)
        if len(self.recent_results) > self.MAX_IN_MEMORY:
            self.recent_results.pop(0)

        # JSONファイルに永続化
        filepath = self.results_dir / f"{result.run_id}.json"
        filepath.write_text(
            json.dumps(result.to_json(), indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    def get(self, run_id: str) -> Optional[RunResult]:
        """run_idで結果を取得する。
        
        まずインメモリキャッシュを検索し、見つからなければ
        JSONファイルからの読み込みを試みる。
        
        Args:
            run_id: 取得したいテスト実行のID
            
        Returns:
            RunResultオブジェクト、見つからない場合はNone
        """
        # インメモリキャッシュを検索
        for result in self.recent_results:
            if result.run_id == run_id:
                return result

        # JSONファイルから読み込み
        filepath = self.results_dir / f"{run_id}.json"
        if filepath.exists():
            return self._load_from_file(filepath)

        return None

    def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """直近の実行履歴を取得する。
        
        インメモリキャッシュから最新のものを返す。キャッシュにlimit件未満
        しかない場合は、JSONファイルからも補完する。
        
        Args:
            limit: 取得する最大件数（デフォルト10）
            
        Returns:
            RunResultのJSON表現（to_json()の結果）のリスト。
            新しいものが先頭。
        """
        # インメモリキャッシュから取得（新しい順）
        results = list(reversed(self.recent_results))

        if len(results) >= limit:
            return [r.to_json() for r in results[:limit]]

        # キャッシュが足りない場合はファイルから補完
        cached_ids = {r.run_id for r in self.recent_results}
        file_results = self._load_all_from_files(exclude_ids=cached_ids)

        # ファイルから読み込んだ結果を追加（新しい順でソート）
        all_results = results + file_results
        all_results.sort(
            key=lambda r: r.started_at or datetime.min,
            reverse=True
        )

        return [r.to_json() for r in all_results[:limit]]

    def _load_from_file(self, filepath: Path) -> Optional[RunResult]:
        """JSONファイルからRunResultを復元する。
        
        Args:
            filepath: JSONファイルのパス
            
        Returns:
            復元したRunResultオブジェクト、読み込み失敗時はNone
        """
        try:
            data = json.loads(filepath.read_text(encoding="utf-8"))
            return self._dict_to_run_result(data)
        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    def _load_all_from_files(self, exclude_ids: set = None) -> List[RunResult]:
        """全JSONファイルからRunResultを読み込む。
        
        Args:
            exclude_ids: 除外するrun_idのセット
            
        Returns:
            RunResultオブジェクトのリスト
        """
        exclude_ids = exclude_ids or set()
        results = []

        if not self.results_dir.exists():
            return results

        for filepath in self.results_dir.glob("*.json"):
            run_id = filepath.stem
            if run_id in exclude_ids:
                continue
            result = self._load_from_file(filepath)
            if result:
                results.append(result)

        return results

    @staticmethod
    def _dict_to_run_result(data: Dict[str, Any]) -> RunResult:
        """JSON辞書からRunResultオブジェクトを復元する。
        
        Args:
            data: to_json()で生成されたJSON辞書
            
        Returns:
            復元したRunResultオブジェクト
        """
        scenarios = []
        for s_data in data.get("scenarios", []):
            steps = []
            for step_data in s_data.get("steps", []):
                steps.append(StepResult(
                    action=step_data["action"],
                    target=step_data["target"],
                    success=step_data["success"],
                    duration_ms=step_data.get("duration_ms", 0.0),
                    error_message=step_data.get("error_message"),
                    load_time_ms=step_data.get("load_time_ms"),
                ))
            scenarios.append(ScenarioResult(
                name=s_data["name"],
                status=TestStatus(s_data["status"]),
                steps=steps,
                duration_seconds=s_data.get("duration_seconds", 0.0),
                error_message=s_data.get("error_message"),
                expected_events=s_data.get("expected_events", {}),
            ))

        started_at = None
        if data.get("started_at"):
            started_at = datetime.fromisoformat(data["started_at"])

        completed_at = None
        if data.get("completed_at"):
            completed_at = datetime.fromisoformat(data["completed_at"])

        return RunResult(
            run_id=data["run_id"],
            status=TestStatus(data["status"]),
            started_at=started_at,
            completed_at=completed_at,
            scenarios=scenarios,
        )
