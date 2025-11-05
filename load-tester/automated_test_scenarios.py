"""
自動化されたテストシナリオ
分散トレーシング、Custom Attribute、パフォーマンス問題の自動検証を実行
"""
import asyncio
import time
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import json
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from distributed_service_client import SyncDistributedServiceTestClient
from newrelic_verification import verification_service
from config import config_manager
from user_session_manager import UserSessionManager

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class TestScenarioResult:
    """テストシナリオの実行結果"""
    scenario_name: str
    status: str  # success, failed, error
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    test_users_count: int
    requests_sent: int
    successful_requests: int
    failed_requests: int
    average_response_time: float
    error_messages: List[str]
    newrelic_verification: Dict[str, Any]

@dataclass
class AutomatedTestSuite:
    """自動化テストスイートの設定"""
    name: str
    scenarios: List[str]
    test_users_count: int
    verification_enabled: bool
    verification_wait_time: int
    max_concurrent_requests: int

class DistributedTracingTestScenarios:
    """分散トレーシング自動テストシナリオ"""
    
    def __init__(self):
        self.config = config_manager.get_config()
        self.distributed_config = self.config.get("distributed_service", {})
        self.client = SyncDistributedServiceTestClient(self.config)
        self.user_manager = UserSessionManager(self.config)
        self.verification_enabled = verification_service.is_enabled()
        
    def _generate_test_users(self, count: int) -> List[Dict[str, Any]]:
        """テスト用ユーザーを生成"""
        user_id_range = self.distributed_config.get("user_id_range", [1, 100])
        start_id, end_id = user_id_range
        
        test_users = []
        for i in range(count):
            user_id = start_id + (i % (end_id - start_id + 1))
            test_users.append({
                "user_id": user_id,
                "username": f"testuser_{user_id}@example.com",
                "session_data": {}
            })
        
        return test_users
    
    async def run_basic_distributed_tracing_test(self, 
                                               test_users_count: int = 5) -> TestScenarioResult:
        """基本的な分散トレーシング機能のテスト"""
        scenario_name = "basic_distributed_tracing"
        start_time = datetime.now()
        
        logger.info(f"Starting {scenario_name} test with {test_users_count} users")
        
        test_users = self._generate_test_users(test_users_count)
        requests_sent = 0
        successful_requests = 0
        failed_requests = 0
        response_times = []
        error_messages = []
        
        try:
            # 各ユーザーで基本的な分散サービス呼び出しを実行
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = []
                
                for user in test_users:
                    # メインアプリ経由での呼び出し
                    future = executor.submit(
                        self.client.test_via_main_app,
                        "n-plus-one",
                        user["user_id"]
                    )
                    futures.append((future, user["user_id"], "via_main_app"))
                    
                    # 直接呼び出し
                    future = executor.submit(
                        self.client.test_direct_call,
                        "n-plus-one", 
                        user["user_id"]
                    )
                    futures.append((future, user["user_id"], "direct"))
                
                # 結果の収集
                for future, user_id, call_type in futures:
                    requests_sent += 1
                    try:
                        result = future.result(timeout=30)
                        if result.get("status") == "success":
                            successful_requests += 1
                            response_times.append(result.get("response_time", 0))
                        else:
                            failed_requests += 1
                            error_messages.append(
                                f"User {user_id} ({call_type}): {result.get('error', 'Unknown error')}"
                            )
                    except Exception as e:
                        failed_requests += 1
                        error_messages.append(f"User {user_id} ({call_type}): {str(e)}")
            
            # New Relic検証（有効な場合）
            newrelic_verification = {}
            if self.verification_enabled:
                logger.info("Running New Relic verification...")
                user_ids = [user["user_id"] for user in test_users]
                
                # 分散トレーシング検証
                trace_results = verification_service.verify_distributed_trace_propagation(
                    test_user_ids=user_ids,
                    wait_time_seconds=60
                )
                
                # Custom Attribute検証
                attribute_results = verification_service.verify_custom_attributes(
                    expected_user_ids=user_ids,
                    wait_time_seconds=30
                )
                
                newrelic_verification = {
                    "trace_propagation": trace_results,
                    "custom_attributes": attribute_results
                }
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 成功判定
            status = "success" if successful_requests > 0 else "failed"
            if self.verification_enabled:
                trace_success = newrelic_verification.get("trace_propagation", {}).get("trace_propagation_success", False)
                attr_success = newrelic_verification.get("custom_attributes", {}).get("verification_success", False)
                if not (trace_success and attr_success):
                    status = "partial" if successful_requests > 0 else "failed"
            
            result = TestScenarioResult(
                scenario_name=scenario_name,
                status=status,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                test_users_count=test_users_count,
                requests_sent=requests_sent,
                successful_requests=successful_requests,
                failed_requests=failed_requests,
                average_response_time=sum(response_times) / len(response_times) if response_times else 0,
                error_messages=error_messages,
                newrelic_verification=newrelic_verification
            )
            
            logger.info(f"Completed {scenario_name} test: {status} "
                       f"({successful_requests}/{requests_sent} successful)")
            
            return result
            
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            logger.error(f"Error in {scenario_name} test: {e}")
            
            return TestScenarioResult(
                scenario_name=scenario_name,
                status="error",
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                test_users_count=test_users_count,
                requests_sent=requests_sent,
                successful_requests=successful_requests,
                failed_requests=failed_requests,
                average_response_time=0,
                error_messages=[str(e)],
                newrelic_verification={}
            )
    
    async def run_n_plus_one_verification_test(self, 
                                             test_users_count: int = 3) -> TestScenarioResult:
        """N+1クエリ問題の自動検証テスト"""
        scenario_name = "n_plus_one_verification"
        start_time = datetime.now()
        
        logger.info(f"Starting {scenario_name} test with {test_users_count} users")
        
        test_users = self._generate_test_users(test_users_count)
        requests_sent = 0
        successful_requests = 0
        failed_requests = 0
        response_times = []
        error_messages = []
        
        try:
            # N+1クエリエンドポイントを集中的にテスト
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = []
                
                for user in test_users:
                    # 複数回のN+1クエリ呼び出し
                    for _ in range(3):
                        future = executor.submit(
                            self.client.test_direct_call,
                            "n-plus-one",
                            user["user_id"]
                        )
                        futures.append((future, user["user_id"]))
                        
                        # 少し間隔を空ける
                        time.sleep(0.5)
                
                # 結果の収集
                for future, user_id in futures:
                    requests_sent += 1
                    try:
                        result = future.result(timeout=60)
                        if result.get("status") == "success":
                            successful_requests += 1
                            response_times.append(result.get("response_time", 0))
                        else:
                            failed_requests += 1
                            error_messages.append(
                                f"User {user_id}: {result.get('error', 'Unknown error')}"
                            )
                    except Exception as e:
                        failed_requests += 1
                        error_messages.append(f"User {user_id}: {str(e)}")
            
            # New Relic検証
            newrelic_verification = {}
            if self.verification_enabled:
                logger.info("Running N+1 query verification...")
                
                # パフォーマンス問題の検証
                performance_results = verification_service.verify_performance_scenarios(
                    scenario_names=["n_plus_one"],
                    wait_time_seconds=90
                )
                
                # Custom Attribute検証
                user_ids = [user["user_id"] for user in test_users]
                attribute_results = verification_service.verify_custom_attributes(
                    expected_user_ids=user_ids,
                    wait_time_seconds=30
                )
                
                newrelic_verification = {
                    "performance_scenarios": performance_results,
                    "custom_attributes": attribute_results
                }
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 成功判定
            status = "success" if successful_requests > 0 else "failed"
            if self.verification_enabled:
                perf_success = newrelic_verification.get("performance_scenarios", {}).get("overall_success", False)
                attr_success = newrelic_verification.get("custom_attributes", {}).get("verification_success", False)
                if not (perf_success and attr_success):
                    status = "partial" if successful_requests > 0 else "failed"
            
            result = TestScenarioResult(
                scenario_name=scenario_name,
                status=status,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                test_users_count=test_users_count,
                requests_sent=requests_sent,
                successful_requests=successful_requests,
                failed_requests=failed_requests,
                average_response_time=sum(response_times) / len(response_times) if response_times else 0,
                error_messages=error_messages,
                newrelic_verification=newrelic_verification
            )
            
            logger.info(f"Completed {scenario_name} test: {status}")
            return result
            
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            logger.error(f"Error in {scenario_name} test: {e}")
            
            return TestScenarioResult(
                scenario_name=scenario_name,
                status="error",
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                test_users_count=test_users_count,
                requests_sent=requests_sent,
                successful_requests=successful_requests,
                failed_requests=failed_requests,
                average_response_time=0,
                error_messages=[str(e)],
                newrelic_verification={}
            )
    
    async def run_slow_query_verification_test(self, 
                                             test_users_count: int = 2) -> TestScenarioResult:
        """スロークエリ問題の自動検証テスト"""
        scenario_name = "slow_query_verification"
        start_time = datetime.now()
        
        logger.info(f"Starting {scenario_name} test with {test_users_count} users")
        
        test_users = self._generate_test_users(test_users_count)
        requests_sent = 0
        successful_requests = 0
        failed_requests = 0
        response_times = []
        error_messages = []
        
        try:
            # スロークエリエンドポイントをテスト
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = []
                
                for user in test_users:
                    # スロークエリ呼び出し
                    for _ in range(2):
                        future = executor.submit(
                            self.client.test_direct_call,
                            "slow-query",
                            user["user_id"]
                        )
                        futures.append((future, user["user_id"]))
                        
                        # 間隔を空ける
                        time.sleep(1.0)
                
                # 結果の収集
                for future, user_id in futures:
                    requests_sent += 1
                    try:
                        result = future.result(timeout=120)  # スロークエリなので長めのタイムアウト
                        if result.get("status") == "success":
                            successful_requests += 1
                            response_times.append(result.get("response_time", 0))
                        else:
                            failed_requests += 1
                            error_messages.append(
                                f"User {user_id}: {result.get('error', 'Unknown error')}"
                            )
                    except Exception as e:
                        failed_requests += 1
                        error_messages.append(f"User {user_id}: {str(e)}")
            
            # New Relic検証
            newrelic_verification = {}
            if self.verification_enabled:
                logger.info("Running slow query verification...")
                
                # パフォーマンス問題の検証
                performance_results = verification_service.verify_performance_scenarios(
                    scenario_names=["slow_query"],
                    wait_time_seconds=120
                )
                
                # Custom Attribute検証
                user_ids = [user["user_id"] for user in test_users]
                attribute_results = verification_service.verify_custom_attributes(
                    expected_user_ids=user_ids,
                    wait_time_seconds=30
                )
                
                newrelic_verification = {
                    "performance_scenarios": performance_results,
                    "custom_attributes": attribute_results
                }
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 成功判定
            status = "success" if successful_requests > 0 else "failed"
            if self.verification_enabled:
                perf_success = newrelic_verification.get("performance_scenarios", {}).get("overall_success", False)
                attr_success = newrelic_verification.get("custom_attributes", {}).get("verification_success", False)
                if not (perf_success and attr_success):
                    status = "partial" if successful_requests > 0 else "failed"
            
            result = TestScenarioResult(
                scenario_name=scenario_name,
                status=status,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                test_users_count=test_users_count,
                requests_sent=requests_sent,
                successful_requests=successful_requests,
                failed_requests=failed_requests,
                average_response_time=sum(response_times) / len(response_times) if response_times else 0,
                error_messages=error_messages,
                newrelic_verification=newrelic_verification
            )
            
            logger.info(f"Completed {scenario_name} test: {status}")
            return result
            
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            logger.error(f"Error in {scenario_name} test: {e}")
            
            return TestScenarioResult(
                scenario_name=scenario_name,
                status="error",
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                test_users_count=test_users_count,
                requests_sent=requests_sent,
                successful_requests=successful_requests,
                failed_requests=failed_requests,
                average_response_time=0,
                error_messages=[str(e)],
                newrelic_verification={}
            )
    
    async def run_database_error_verification_test(self, 
                                                 test_users_count: int = 2) -> TestScenarioResult:
        """データベースエラー問題の自動検証テスト"""
        scenario_name = "database_error_verification"
        start_time = datetime.now()
        
        logger.info(f"Starting {scenario_name} test with {test_users_count} users")
        
        test_users = self._generate_test_users(test_users_count)
        requests_sent = 0
        successful_requests = 0
        failed_requests = 0
        response_times = []
        error_messages = []
        
        try:
            # データベースエラーエンドポイントをテスト
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = []
                
                for user in test_users:
                    # データベースエラー呼び出し
                    for _ in range(2):
                        future = executor.submit(
                            self.client.test_direct_call,
                            "database-error",
                            user["user_id"]
                        )
                        futures.append((future, user["user_id"]))
                        
                        time.sleep(0.5)
                
                # 結果の収集（エラーが期待される）
                for future, user_id in futures:
                    requests_sent += 1
                    try:
                        result = future.result(timeout=30)
                        # データベースエラーの場合、エラーレスポンスも成功とみなす
                        if result.get("status") in ["success", "error"]:
                            successful_requests += 1
                            response_times.append(result.get("response_time", 0))
                        else:
                            failed_requests += 1
                            error_messages.append(
                                f"User {user_id}: {result.get('error', 'Unknown error')}"
                            )
                    except Exception as e:
                        failed_requests += 1
                        error_messages.append(f"User {user_id}: {str(e)}")
            
            # New Relic検証
            newrelic_verification = {}
            if self.verification_enabled:
                logger.info("Running database error verification...")
                
                # パフォーマンス問題の検証
                performance_results = verification_service.verify_performance_scenarios(
                    scenario_names=["database_error"],
                    wait_time_seconds=90
                )
                
                # Custom Attribute検証
                user_ids = [user["user_id"] for user in test_users]
                attribute_results = verification_service.verify_custom_attributes(
                    expected_user_ids=user_ids,
                    wait_time_seconds=30
                )
                
                newrelic_verification = {
                    "performance_scenarios": performance_results,
                    "custom_attributes": attribute_results
                }
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 成功判定
            status = "success" if successful_requests > 0 else "failed"
            if self.verification_enabled:
                perf_success = newrelic_verification.get("performance_scenarios", {}).get("overall_success", False)
                attr_success = newrelic_verification.get("custom_attributes", {}).get("verification_success", False)
                if not (perf_success and attr_success):
                    status = "partial" if successful_requests > 0 else "failed"
            
            result = TestScenarioResult(
                scenario_name=scenario_name,
                status=status,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                test_users_count=test_users_count,
                requests_sent=requests_sent,
                successful_requests=successful_requests,
                failed_requests=failed_requests,
                average_response_time=sum(response_times) / len(response_times) if response_times else 0,
                error_messages=error_messages,
                newrelic_verification=newrelic_verification
            )
            
            logger.info(f"Completed {scenario_name} test: {status}")
            return result
            
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            logger.error(f"Error in {scenario_name} test: {e}")
            
            return TestScenarioResult(
                scenario_name=scenario_name,
                status="error",
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                test_users_count=test_users_count,
                requests_sent=requests_sent,
                successful_requests=successful_requests,
                failed_requests=failed_requests,
                average_response_time=0,
                error_messages=[str(e)],
                newrelic_verification={}
            )

class AutomatedTestRunner:
    """自動化テストランナー"""
    
    def __init__(self):
        self.scenarios = DistributedTracingTestScenarios()
        self.config = config_manager.get_config()
        
    async def run_test_suite(self, suite_config: AutomatedTestSuite) -> Dict[str, Any]:
        """テストスイートを実行"""
        logger.info(f"Starting automated test suite: {suite_config.name}")
        
        suite_start_time = datetime.now()
        results = []
        
        try:
            # 各シナリオを順次実行
            for scenario_name in suite_config.scenarios:
                logger.info(f"Running scenario: {scenario_name}")
                
                if scenario_name == "basic_distributed_tracing":
                    result = await self.scenarios.run_basic_distributed_tracing_test(
                        test_users_count=suite_config.test_users_count
                    )
                elif scenario_name == "n_plus_one_verification":
                    result = await self.scenarios.run_n_plus_one_verification_test(
                        test_users_count=min(suite_config.test_users_count, 3)
                    )
                elif scenario_name == "slow_query_verification":
                    result = await self.scenarios.run_slow_query_verification_test(
                        test_users_count=min(suite_config.test_users_count, 2)
                    )
                elif scenario_name == "database_error_verification":
                    result = await self.scenarios.run_database_error_verification_test(
                        test_users_count=min(suite_config.test_users_count, 2)
                    )
                else:
                    logger.warning(f"Unknown scenario: {scenario_name}")
                    continue
                
                results.append(result)
                
                # シナリオ間の間隔
                await asyncio.sleep(5)
            
            suite_end_time = datetime.now()
            suite_duration = (suite_end_time - suite_start_time).total_seconds()
            
            # 総合結果の生成
            total_requests = sum(r.requests_sent for r in results)
            total_successful = sum(r.successful_requests for r in results)
            total_failed = sum(r.failed_requests for r in results)
            
            successful_scenarios = sum(1 for r in results if r.status == "success")
            partial_scenarios = sum(1 for r in results if r.status == "partial")
            failed_scenarios = sum(1 for r in results if r.status in ["failed", "error"])
            
            overall_status = "success"
            if failed_scenarios > 0:
                overall_status = "partial" if successful_scenarios > 0 else "failed"
            
            # New Relic検証の総合レポート生成
            comprehensive_report = {}
            if suite_config.verification_enabled and verification_service.is_enabled():
                # 各シナリオの検証結果を統合
                all_trace_results = {}
                all_attribute_results = {}
                all_performance_results = {}
                
                for result in results:
                    nr_verification = result.newrelic_verification
                    if "trace_propagation" in nr_verification:
                        all_trace_results[result.scenario_name] = nr_verification["trace_propagation"]
                    if "custom_attributes" in nr_verification:
                        all_attribute_results[result.scenario_name] = nr_verification["custom_attributes"]
                    if "performance_scenarios" in nr_verification:
                        all_performance_results[result.scenario_name] = nr_verification["performance_scenarios"]
                
                comprehensive_report = verification_service.generate_verification_report(
                    trace_results=all_trace_results,
                    attribute_results=all_attribute_results,
                    performance_results=all_performance_results
                )
            
            suite_result = {
                "suite_name": suite_config.name,
                "overall_status": overall_status,
                "start_time": suite_start_time.isoformat(),
                "end_time": suite_end_time.isoformat(),
                "duration_seconds": suite_duration,
                "summary": {
                    "total_scenarios": len(results),
                    "successful_scenarios": successful_scenarios,
                    "partial_scenarios": partial_scenarios,
                    "failed_scenarios": failed_scenarios,
                    "total_requests": total_requests,
                    "successful_requests": total_successful,
                    "failed_requests": total_failed,
                    "success_rate": total_successful / total_requests if total_requests > 0 else 0
                },
                "scenario_results": [asdict(result) for result in results],
                "newrelic_comprehensive_report": comprehensive_report
            }
            
            logger.info(f"Completed test suite: {suite_config.name} - {overall_status}")
            logger.info(f"Summary: {successful_scenarios}/{len(results)} scenarios successful, "
                       f"{total_successful}/{total_requests} requests successful")
            
            return suite_result
            
        except Exception as e:
            suite_end_time = datetime.now()
            suite_duration = (suite_end_time - suite_start_time).total_seconds()
            
            logger.error(f"Error in test suite {suite_config.name}: {e}")
            
            return {
                "suite_name": suite_config.name,
                "overall_status": "error",
                "start_time": suite_start_time.isoformat(),
                "end_time": suite_end_time.isoformat(),
                "duration_seconds": suite_duration,
                "error": str(e),
                "scenario_results": [asdict(result) for result in results],
                "newrelic_comprehensive_report": {}
            }
    
    def save_test_results(self, results: Dict[str, Any], filename: Optional[str] = None):
        """テスト結果をファイルに保存"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"logs/automated_test_results_{timestamp}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False, default=str)
            logger.info(f"Test results saved to {filename}")
        except Exception as e:
            logger.error(f"Failed to save test results: {e}")

# 事前定義されたテストスイート
PREDEFINED_TEST_SUITES = {
    "basic_verification": AutomatedTestSuite(
        name="Basic Distributed Tracing Verification",
        scenarios=["basic_distributed_tracing"],
        test_users_count=5,
        verification_enabled=True,
        verification_wait_time=60,
        max_concurrent_requests=10
    ),
    "performance_verification": AutomatedTestSuite(
        name="Performance Issues Verification",
        scenarios=["n_plus_one_verification", "slow_query_verification", "database_error_verification"],
        test_users_count=3,
        verification_enabled=True,
        verification_wait_time=120,
        max_concurrent_requests=5
    ),
    "comprehensive_verification": AutomatedTestSuite(
        name="Comprehensive Distributed Tracing Verification",
        scenarios=[
            "basic_distributed_tracing",
            "n_plus_one_verification", 
            "slow_query_verification",
            "database_error_verification"
        ],
        test_users_count=5,
        verification_enabled=True,
        verification_wait_time=120,
        max_concurrent_requests=8
    )
}

# グローバルインスタンス
test_runner = AutomatedTestRunner()