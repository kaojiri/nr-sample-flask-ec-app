"""
分散サービステストシナリオ
様々な負荷テストシナリオと複数ユーザー同時アクセスシナリオを提供
"""
import asyncio
import logging
import random
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from distributed_service_client import (
    DistributedServiceTestClient, 
    DistributedTestResult,
    distributed_test_logger
)
from config import config_manager

logger = logging.getLogger(__name__)

class ScenarioType(Enum):
    """テストシナリオの種類"""
    BASIC_DISTRIBUTED_TRACING = "basic_distributed_tracing"
    N_PLUS_ONE_LOAD_TEST = "n_plus_one_load_test"
    SLOW_QUERY_LOAD_TEST = "slow_query_load_test"
    DATABASE_ERROR_TEST = "database_error_test"
    CONCURRENT_USERS_TEST = "concurrent_users_test"
    COMPREHENSIVE_TEST = "comprehensive_test"

@dataclass
class ScenarioConfig:
    """テストシナリオの設定"""
    scenario_type: ScenarioType
    concurrent_users: int = 10
    duration_minutes: int = 5
    ramp_up_seconds: int = 30
    request_interval_min: float = 1.0
    request_interval_max: float = 3.0
    call_type: str = "direct"  # "direct" or "via_main_app"
    include_trace_headers: bool = True
    timeout_seconds: Optional[int] = None
    user_id_range: tuple = (1, 100)
    parameters: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """設定の検証と調整"""
        if self.concurrent_users <= 0:
            self.concurrent_users = 1
        if self.duration_minutes <= 0:
            self.duration_minutes = 1
        if self.request_interval_min >= self.request_interval_max:
            self.request_interval_max = self.request_interval_min + 1.0

@dataclass
class ScenarioResult:
    """テストシナリオの実行結果"""
    scenario_type: ScenarioType
    config: ScenarioConfig
    start_time: datetime
    end_time: Optional[datetime] = None
    test_results: List[DistributedTestResult] = field(default_factory=list)
    worker_results: Dict[str, List[DistributedTestResult]] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    
    @property
    def duration_seconds(self) -> float:
        """実行時間（秒）"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0
    
    @property
    def total_requests(self) -> int:
        """総リクエスト数"""
        return len(self.test_results)
    
    @property
    def successful_requests(self) -> int:
        """成功したリクエスト数"""
        return sum(1 for result in self.test_results if result.is_success)
    
    @property
    def failed_requests(self) -> int:
        """失敗したリクエスト数"""
        return self.total_requests - self.successful_requests
    
    @property
    def success_rate(self) -> float:
        """成功率（%）"""
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100
    
    @property
    def average_response_time(self) -> float:
        """平均レスポンス時間（秒）"""
        if not self.test_results:
            return 0.0
        total_time = sum(result.total_response_time for result in self.test_results)
        return total_time / len(self.test_results)
    
    @property
    def requests_per_second(self) -> float:
        """1秒あたりのリクエスト数"""
        if self.duration_seconds == 0:
            return 0.0
        return self.total_requests / self.duration_seconds

class DistributedTestScenarios:
    """
    分散サービステストシナリオの実行クラス
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初期化
        
        Args:
            config: 設定辞書（Noneの場合はconfig_managerから取得）
        """
        self.config = config or config_manager.get_config()
        self.running_scenarios: Dict[str, bool] = {}
        self.scenario_results: List[ScenarioResult] = []
    
    async def basic_distributed_tracing_test(self, 
                                           config: Optional[ScenarioConfig] = None) -> ScenarioResult:
        """
        基本的な分散トレーシング機能の負荷テスト
        設定された時間とユーザー数で各エンドポイントをテスト
        
        Args:
            config: シナリオ設定
            
        Returns:
            ScenarioResult: テスト結果
        """
        if config is None:
            config = ScenarioConfig(
                scenario_type=ScenarioType.BASIC_DISTRIBUTED_TRACING,
                concurrent_users=1,
                duration_minutes=1,
                call_type="direct"
            )
        
        logger.info(f"Starting basic distributed tracing test: {config.concurrent_users} users, {config.duration_minutes} minutes")
        result = ScenarioResult(
            scenario_type=ScenarioType.BASIC_DISTRIBUTED_TRACING,
            config=config,
            start_time=datetime.now()
        )
        
        try:
            # 複数ユーザーでの負荷テストを実行
            tasks = []
            
            for user_index in range(config.concurrent_users):
                # ランプアップ時間を考慮した開始遅延
                start_delay = (user_index * config.ramp_up_seconds) / config.concurrent_users if config.concurrent_users > 1 else 0
                
                task = asyncio.create_task(
                    self._run_basic_tracing_user_session(
                        config=config,
                        user_index=user_index,
                        start_delay=start_delay,
                        result=result
                    )
                )
                tasks.append(task)
            
            # 全ユーザーセッションの完了を待機
            await asyncio.gather(*tasks, return_exceptions=True)
        
        except Exception as e:
            error_msg = f"Error in basic distributed tracing test: {e}"
            logger.error(error_msg)
            result.errors.append(error_msg)
        
        result.end_time = datetime.now()
        self.scenario_results.append(result)
        
        logger.info(f"Basic distributed tracing test completed. "
                   f"Success rate: {result.success_rate:.1f}%, "
                   f"Total requests: {result.total_requests}, "
                   f"Duration: {result.duration_seconds:.1f}s")
        
        return result
    
    async def _run_basic_tracing_user_session(self, 
                                            config: ScenarioConfig,
                                            user_index: int,
                                            start_delay: float,
                                            result: ScenarioResult):
        """
        基本分散トレーシングテストの個別ユーザーセッション
        
        Args:
            config: シナリオ設定
            user_index: ユーザーインデックス
            start_delay: 開始遅延時間
            result: 結果オブジェクト
        """
        try:
            # 開始遅延
            if start_delay > 0:
                await asyncio.sleep(start_delay)
            
            async with DistributedServiceTestClient(self.config) as client:
                user_id = random.randint(*config.user_id_range)
                endpoints = ["n-plus-one", "slow-query", "database-error"]
                
                # テスト実行時間を計算
                end_time = datetime.now() + timedelta(minutes=config.duration_minutes)
                
                while datetime.now() < end_time:
                    # ランダムにエンドポイントを選択
                    endpoint = random.choice(endpoints)
                    
                    try:
                        if config.call_type == "direct":
                            test_result = await client.test_direct_call(
                                endpoint=endpoint,
                                user_id=user_id,
                                include_trace_headers=config.include_trace_headers,
                                timeout=config.timeout_seconds
                            )
                        elif config.call_type == "via_main_app":
                            test_result = await client.test_via_main_app(
                                endpoint=endpoint,
                                user_id=user_id,
                                include_trace_headers=config.include_trace_headers,
                                timeout=config.timeout_seconds
                            )
                        else:  # both
                            # 50%の確率でdirectまたはvia_main_appを選択
                            if random.random() < 0.5:
                                test_result = await client.test_direct_call(
                                    endpoint=endpoint,
                                    user_id=user_id,
                                    include_trace_headers=config.include_trace_headers,
                                    timeout=config.timeout_seconds
                                )
                            else:
                                test_result = await client.test_via_main_app(
                                    endpoint=endpoint,
                                    user_id=user_id,
                                    include_trace_headers=config.include_trace_headers,
                                    timeout=config.timeout_seconds
                                )
                        
                        result.test_results.append(test_result)
                        distributed_test_logger.log_test_result(test_result)
                        
                        # リクエスト間隔の待機
                        interval = random.uniform(config.request_interval_min, config.request_interval_max)
                        await asyncio.sleep(interval)
                        
                    except Exception as e:
                        error_msg = f"Error testing endpoint {endpoint} for user {user_index}: {e}"
                        logger.error(error_msg)
                        result.errors.append(error_msg)
                        
                        # エラー時も少し待機
                        await asyncio.sleep(1.0)
        
        except Exception as e:
            error_msg = f"Error in user session {user_index}: {e}"
            logger.error(error_msg)
            result.errors.append(error_msg)
    
    async def n_plus_one_load_test(self, 
                                  config: Optional[ScenarioConfig] = None) -> ScenarioResult:
        """
        N+1クエリ問題の負荷テストシナリオ
        
        Args:
            config: シナリオ設定
            
        Returns:
            ScenarioResult: テスト結果
        """
        if config is None:
            config = ScenarioConfig(
                scenario_type=ScenarioType.N_PLUS_ONE_LOAD_TEST,
                concurrent_users=10,
                duration_minutes=5,
                ramp_up_seconds=30,
                call_type="direct",
                timeout_seconds=60
            )
        
        logger.info(f"Starting N+1 query load test with {config.concurrent_users} users")
        
        return await self._run_load_test_scenario(
            scenario_type=ScenarioType.N_PLUS_ONE_LOAD_TEST,
            config=config,
            test_function=self._n_plus_one_test_worker
        )
    
    async def slow_query_load_test(self, 
                                  config: Optional[ScenarioConfig] = None) -> ScenarioResult:
        """
        スロークエリの負荷テストシナリオ
        
        Args:
            config: シナリオ設定
            
        Returns:
            ScenarioResult: テスト結果
        """
        if config is None:
            config = ScenarioConfig(
                scenario_type=ScenarioType.SLOW_QUERY_LOAD_TEST,
                concurrent_users=5,
                duration_minutes=3,
                ramp_up_seconds=20,
                call_type="direct",
                timeout_seconds=120
            )
        
        logger.info(f"Starting slow query load test with {config.concurrent_users} users")
        
        return await self._run_load_test_scenario(
            scenario_type=ScenarioType.SLOW_QUERY_LOAD_TEST,
            config=config,
            test_function=self._slow_query_test_worker
        )
    
    async def database_error_test(self, 
                                 config: Optional[ScenarioConfig] = None) -> ScenarioResult:
        """
        データベースエラーの負荷テストシナリオ
        
        Args:
            config: シナリオ設定
            
        Returns:
            ScenarioResult: テスト結果
        """
        if config is None:
            config = ScenarioConfig(
                scenario_type=ScenarioType.DATABASE_ERROR_TEST,
                concurrent_users=3,
                duration_minutes=2,
                ramp_up_seconds=10,
                call_type="direct",
                timeout_seconds=30
            )
        
        logger.info(f"Starting database error test with {config.concurrent_users} users")
        
        return await self._run_load_test_scenario(
            scenario_type=ScenarioType.DATABASE_ERROR_TEST,
            config=config,
            test_function=self._database_error_test_worker
        )
    
    async def concurrent_users_test(self, 
                                   config: Optional[ScenarioConfig] = None) -> ScenarioResult:
        """
        複数ユーザー同時アクセスシナリオ
        全エンドポイントに対して複数ユーザーが同時にアクセス
        
        Args:
            config: シナリオ設定
            
        Returns:
            ScenarioResult: テスト結果
        """
        if config is None:
            config = ScenarioConfig(
                scenario_type=ScenarioType.CONCURRENT_USERS_TEST,
                concurrent_users=15,
                duration_minutes=10,
                ramp_up_seconds=60,
                call_type="via_main_app",
                timeout_seconds=90
            )
        
        logger.info(f"Starting concurrent users test with {config.concurrent_users} users")
        
        return await self._run_load_test_scenario(
            scenario_type=ScenarioType.CONCURRENT_USERS_TEST,
            config=config,
            test_function=self._concurrent_users_test_worker
        )
    
    async def comprehensive_test(self, 
                                config: Optional[ScenarioConfig] = None) -> ScenarioResult:
        """
        包括的テストシナリオ
        全エンドポイントを順次テストし、直接呼び出しとメインアプリ経由の両方をテスト
        
        Args:
            config: シナリオ設定
            
        Returns:
            ScenarioResult: テスト結果
        """
        if config is None:
            config = ScenarioConfig(
                scenario_type=ScenarioType.COMPREHENSIVE_TEST,
                concurrent_users=8,
                duration_minutes=15,
                ramp_up_seconds=45,
                call_type="both",  # 特別な値
                timeout_seconds=120
            )
        
        logger.info(f"Starting comprehensive test with {config.concurrent_users} users")
        
        return await self._run_load_test_scenario(
            scenario_type=ScenarioType.COMPREHENSIVE_TEST,
            config=config,
            test_function=self._comprehensive_test_worker
        )
    
    async def _run_load_test_scenario(self,
                                     scenario_type: ScenarioType,
                                     config: ScenarioConfig,
                                     test_function: Callable) -> ScenarioResult:
        """
        負荷テストシナリオの共通実行ロジック
        
        Args:
            scenario_type: シナリオタイプ
            config: シナリオ設定
            test_function: テスト関数
            
        Returns:
            ScenarioResult: テスト結果
        """
        result = ScenarioResult(
            scenario_type=scenario_type,
            config=config,
            start_time=datetime.now()
        )
        
        scenario_id = f"{scenario_type.value}_{int(time.time())}"
        self.running_scenarios[scenario_id] = True
        
        try:
            # ワーカータスクを作成
            tasks = []
            for worker_id in range(config.concurrent_users):
                task = asyncio.create_task(
                    self._worker_with_ramp_up(
                        worker_id=f"worker_{worker_id}",
                        scenario_id=scenario_id,
                        config=config,
                        test_function=test_function,
                        result=result
                    )
                )
                tasks.append(task)
                
                # ランプアップ待機
                if config.ramp_up_seconds > 0:
                    ramp_up_delay = config.ramp_up_seconds / config.concurrent_users
                    await asyncio.sleep(ramp_up_delay)
            
            # 全ワーカーの完了を待機
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            error_msg = f"Error in load test scenario {scenario_type.value}: {e}"
            logger.error(error_msg)
            result.errors.append(error_msg)
        
        finally:
            self.running_scenarios[scenario_id] = False
        
        result.end_time = datetime.now()
        self.scenario_results.append(result)
        
        logger.info(f"Load test scenario {scenario_type.value} completed. "
                   f"Success rate: {result.success_rate:.1f}%, "
                   f"Total requests: {result.total_requests}, "
                   f"RPS: {result.requests_per_second:.2f}")
        
        return result
    
    async def _worker_with_ramp_up(self,
                                  worker_id: str,
                                  scenario_id: str,
                                  config: ScenarioConfig,
                                  test_function: Callable,
                                  result: ScenarioResult):
        """
        ランプアップ機能付きワーカー
        
        Args:
            worker_id: ワーカーID
            scenario_id: シナリオID
            config: シナリオ設定
            test_function: テスト関数
            result: 結果オブジェクト
        """
        worker_results = []
        end_time = datetime.now() + timedelta(minutes=config.duration_minutes)
        
        logger.debug(f"Worker {worker_id} started for scenario {scenario_id}")
        
        try:
            async with DistributedServiceTestClient(self.config) as client:
                while (datetime.now() < end_time and 
                       self.running_scenarios.get(scenario_id, False)):
                    
                    try:
                        # テスト関数を実行
                        test_result = await test_function(client, config)
                        
                        if test_result:
                            worker_results.append(test_result)
                            result.test_results.append(test_result)
                            distributed_test_logger.log_test_result(test_result)
                        
                        # リクエスト間隔の待機
                        interval = random.uniform(
                            config.request_interval_min,
                            config.request_interval_max
                        )
                        await asyncio.sleep(interval)
                        
                    except Exception as e:
                        error_msg = f"Worker {worker_id} error: {e}"
                        logger.error(error_msg)
                        result.errors.append(error_msg)
                        await asyncio.sleep(1.0)  # エラー時は少し待機
        
        except Exception as e:
            error_msg = f"Worker {worker_id} fatal error: {e}"
            logger.error(error_msg)
            result.errors.append(error_msg)
        
        result.worker_results[worker_id] = worker_results
        logger.debug(f"Worker {worker_id} completed with {len(worker_results)} requests")
    
    async def _n_plus_one_test_worker(self,
                                     client: DistributedServiceTestClient,
                                     config: ScenarioConfig) -> Optional[DistributedTestResult]:
        """N+1クエリテスト用ワーカー関数"""
        user_id = random.randint(*config.user_id_range)
        
        if config.call_type == "direct":
            return await client.test_n_plus_one_problem(
                user_id=user_id,
                call_type="direct",
                timeout=config.timeout_seconds
            )
        else:
            return await client.test_n_plus_one_problem(
                user_id=user_id,
                call_type="via_main_app",
                timeout=config.timeout_seconds
            )
    
    async def _slow_query_test_worker(self,
                                     client: DistributedServiceTestClient,
                                     config: ScenarioConfig) -> Optional[DistributedTestResult]:
        """スロークエリテスト用ワーカー関数"""
        user_id = random.randint(*config.user_id_range)
        
        if config.call_type == "direct":
            return await client.test_slow_query(
                user_id=user_id,
                call_type="direct",
                timeout=config.timeout_seconds
            )
        else:
            return await client.test_slow_query(
                user_id=user_id,
                call_type="via_main_app",
                timeout=config.timeout_seconds
            )
    
    async def _database_error_test_worker(self,
                                         client: DistributedServiceTestClient,
                                         config: ScenarioConfig) -> Optional[DistributedTestResult]:
        """データベースエラーテスト用ワーカー関数"""
        user_id = random.randint(*config.user_id_range)
        
        if config.call_type == "direct":
            return await client.test_database_error(
                user_id=user_id,
                call_type="direct",
                timeout=config.timeout_seconds
            )
        else:
            return await client.test_database_error(
                user_id=user_id,
                call_type="via_main_app",
                timeout=config.timeout_seconds
            )
    
    async def _concurrent_users_test_worker(self,
                                           client: DistributedServiceTestClient,
                                           config: ScenarioConfig) -> Optional[DistributedTestResult]:
        """複数ユーザー同時アクセステスト用ワーカー関数"""
        user_id = random.randint(*config.user_id_range)
        
        # ランダムにエンドポイントを選択
        endpoints = ["n-plus-one", "slow-query", "database-error"]
        endpoint = random.choice(endpoints)
        
        if config.call_type == "direct":
            return await client.test_direct_call(
                endpoint=endpoint,
                user_id=user_id,
                include_trace_headers=config.include_trace_headers,
                timeout=config.timeout_seconds
            )
        else:
            return await client.test_via_main_app(
                endpoint=endpoint,
                user_id=user_id,
                include_trace_headers=config.include_trace_headers,
                timeout=config.timeout_seconds
            )
    
    async def _comprehensive_test_worker(self,
                                        client: DistributedServiceTestClient,
                                        config: ScenarioConfig) -> Optional[DistributedTestResult]:
        """包括的テスト用ワーカー関数"""
        user_id = random.randint(*config.user_id_range)
        
        # ランダムにエンドポイントと呼び出しタイプを選択
        endpoints = ["n-plus-one", "slow-query", "database-error"]
        endpoint = random.choice(endpoints)
        
        # "both"の場合はランダムに選択
        if config.call_type == "both":
            call_type = random.choice(["direct", "via_main_app"])
        else:
            call_type = config.call_type
        
        if call_type == "direct":
            return await client.test_direct_call(
                endpoint=endpoint,
                user_id=user_id,
                include_trace_headers=config.include_trace_headers,
                timeout=config.timeout_seconds
            )
        else:
            return await client.test_via_main_app(
                endpoint=endpoint,
                user_id=user_id,
                include_trace_headers=config.include_trace_headers,
                timeout=config.timeout_seconds
            )
    
    def stop_scenario(self, scenario_id: str):
        """実行中のシナリオを停止"""
        if scenario_id in self.running_scenarios:
            self.running_scenarios[scenario_id] = False
            logger.info(f"Stopping scenario {scenario_id}")
    
    def stop_all_scenarios(self):
        """全ての実行中シナリオを停止"""
        for scenario_id in list(self.running_scenarios.keys()):
            self.stop_scenario(scenario_id)
        logger.info("Stopping all running scenarios")
    
    def get_scenario_results(self) -> List[ScenarioResult]:
        """全シナリオ結果を取得"""
        return self.scenario_results.copy()
    
    def get_latest_result(self, scenario_type: ScenarioType) -> Optional[ScenarioResult]:
        """指定タイプの最新結果を取得"""
        matching_results = [r for r in self.scenario_results if r.scenario_type == scenario_type]
        if matching_results:
            return max(matching_results, key=lambda r: r.start_time)
        return None
    
    def clear_results(self):
        """結果をクリア"""
        self.scenario_results.clear()
        logger.info("Cleared all scenario results")

class ScenarioRunner:
    """シナリオ実行の管理クラス"""
    
    def __init__(self, config: Optional[Dict] = None):
        self.scenarios = DistributedTestScenarios(config)
    
    async def run_all_scenarios(self) -> Dict[str, ScenarioResult]:
        """全シナリオを順次実行"""
        results = {}
        
        logger.info("Starting comprehensive distributed service test suite")
        
        # 基本テスト
        results["basic"] = await self.scenarios.basic_distributed_tracing_test()
        await asyncio.sleep(5)  # シナリオ間の待機
        
        # N+1クエリ負荷テスト
        results["n_plus_one"] = await self.scenarios.n_plus_one_load_test()
        await asyncio.sleep(5)
        
        # スロークエリ負荷テスト
        results["slow_query"] = await self.scenarios.slow_query_load_test()
        await asyncio.sleep(5)
        
        # データベースエラーテスト
        results["database_error"] = await self.scenarios.database_error_test()
        await asyncio.sleep(5)
        
        # 複数ユーザー同時アクセステスト
        results["concurrent_users"] = await self.scenarios.concurrent_users_test()
        await asyncio.sleep(5)
        
        # 包括的テスト
        results["comprehensive"] = await self.scenarios.comprehensive_test()
        
        logger.info("Completed all distributed service test scenarios")
        
        return results
    
    def generate_summary_report(self, results: Dict[str, ScenarioResult]) -> Dict[str, Any]:
        """サマリーレポートを生成"""
        total_requests = sum(r.total_requests for r in results.values())
        total_successful = sum(r.successful_requests for r in results.values())
        total_failed = sum(r.failed_requests for r in results.values())
        
        avg_success_rate = sum(r.success_rate for r in results.values()) / len(results)
        avg_response_time = sum(r.average_response_time for r in results.values()) / len(results)
        
        return {
            "summary": {
                "total_scenarios": len(results),
                "total_requests": total_requests,
                "total_successful": total_successful,
                "total_failed": total_failed,
                "overall_success_rate": (total_successful / total_requests * 100) if total_requests > 0 else 0,
                "average_success_rate": avg_success_rate,
                "average_response_time": avg_response_time
            },
            "scenario_details": {
                name: {
                    "requests": result.total_requests,
                    "success_rate": result.success_rate,
                    "avg_response_time": result.average_response_time,
                    "duration": result.duration_seconds,
                    "rps": result.requests_per_second,
                    "errors": len(result.errors)
                }
                for name, result in results.items()
            }
        }