"""
分散サービステストのLoad Tester統合
メインのLoad Testerシステムに分散サービステスト機能を統合
"""
import asyncio
import logging
import json
from typing import Dict, List, Optional, Any
from datetime import datetime

from distributed_test_scenarios import (
    DistributedTestScenarios,
    ScenarioRunner,
    ScenarioConfig,
    ScenarioType,
    ScenarioResult
)
from config import config_manager

logger = logging.getLogger(__name__)

class DistributedTestIntegration:
    """
    分散サービステストのLoad Tester統合クラス
    """
    
    def __init__(self):
        self.config = config_manager.get_config()
        self.scenarios = DistributedTestScenarios(self.config)
        self.runner = ScenarioRunner(self.config)
        self.is_running = False
        self.current_scenario = None
    
    def get_available_scenarios(self) -> List[Dict[str, Any]]:
        """利用可能なシナリオのリストを取得"""
        distributed_config = self.config.get("distributed_service", {})
        test_scenarios = distributed_config.get("test_scenarios", {})
        
        scenarios = []
        for scenario_name, scenario_config in test_scenarios.items():
            scenarios.append({
                "name": scenario_name,
                "display_name": self._get_display_name(scenario_name),
                "description": self._get_scenario_description(scenario_name),
                "config": scenario_config,
                "estimated_duration_minutes": scenario_config.get("duration_minutes", 5),
                "concurrent_users": scenario_config.get("concurrent_users", 1)
            })
        
        return scenarios
    
    def _get_display_name(self, scenario_name: str) -> str:
        """シナリオの表示名を取得"""
        display_names = {
            "basic_distributed_tracing": "基本分散トレーシングテスト",
            "n_plus_one_load_test": "N+1クエリ負荷テスト",
            "slow_query_load_test": "スロークエリ負荷テスト",
            "database_error_test": "データベースエラーテスト",
            "concurrent_users_test": "複数ユーザー同時アクセステスト",
            "comprehensive_test": "包括的テスト"
        }
        return display_names.get(scenario_name, scenario_name.replace("_", " ").title())
    
    def _get_scenario_description(self, scenario_name: str) -> str:
        """シナリオの説明を取得"""
        descriptions = {
            "basic_distributed_tracing": "分散トレーシング機能の基本動作を確認するテスト",
            "n_plus_one_load_test": "N+1クエリ問題のエンドポイントに対する負荷テスト",
            "slow_query_load_test": "スロークエリのエンドポイントに対する負荷テスト",
            "database_error_test": "データベースエラーの処理とトレーシングを確認するテスト",
            "concurrent_users_test": "複数ユーザーが同時に分散サービスにアクセスするテスト",
            "comprehensive_test": "全エンドポイントを対象とした包括的な負荷テスト"
        }
        return descriptions.get(scenario_name, "分散サービステストシナリオ")
    
    async def run_scenario(self, scenario_name: str, custom_config: Optional[Dict] = None) -> ScenarioResult:
        """
        指定されたシナリオを実行
        
        Args:
            scenario_name: シナリオ名
            custom_config: カスタム設定（オプション）
            
        Returns:
            ScenarioResult: テスト結果
        """
        if self.is_running:
            raise RuntimeError("Another scenario is already running")
        
        self.is_running = True
        self.current_scenario = scenario_name
        
        try:
            logger.info(f"Starting distributed service test scenario: {scenario_name}")
            
            # 設定の準備
            scenario_config = self._prepare_scenario_config(scenario_name, custom_config)
            
            # シナリオタイプの決定
            scenario_type = self._get_scenario_type(scenario_name)
            
            # シナリオの実行
            if scenario_type == ScenarioType.BASIC_DISTRIBUTED_TRACING:
                result = await self.scenarios.basic_distributed_tracing_test(scenario_config)
            elif scenario_type == ScenarioType.N_PLUS_ONE_LOAD_TEST:
                result = await self.scenarios.n_plus_one_load_test(scenario_config)
            elif scenario_type == ScenarioType.SLOW_QUERY_LOAD_TEST:
                result = await self.scenarios.slow_query_load_test(scenario_config)
            elif scenario_type == ScenarioType.DATABASE_ERROR_TEST:
                result = await self.scenarios.database_error_test(scenario_config)
            elif scenario_type == ScenarioType.CONCURRENT_USERS_TEST:
                result = await self.scenarios.concurrent_users_test(scenario_config)
            elif scenario_type == ScenarioType.COMPREHENSIVE_TEST:
                result = await self.scenarios.comprehensive_test(scenario_config)
            else:
                raise ValueError(f"Unknown scenario type: {scenario_name}")
            
            logger.info(f"Completed distributed service test scenario: {scenario_name}")
            return result
            
        except Exception as e:
            logger.error(f"Error running scenario {scenario_name}: {e}")
            raise
        finally:
            self.is_running = False
            self.current_scenario = None
    
    def _prepare_scenario_config(self, scenario_name: str, custom_config: Optional[Dict]) -> ScenarioConfig:
        """シナリオ設定を準備"""
        # デフォルト設定を取得
        distributed_config = self.config.get("distributed_service", {})
        test_scenarios = distributed_config.get("test_scenarios", {})
        default_config = test_scenarios.get(scenario_name, {})
        
        # ユーザーID範囲を取得
        user_id_range = distributed_config.get("user_id_range", [1, 100])
        
        # 設定をマージ
        final_config = default_config.copy()
        if custom_config:
            final_config.update(custom_config)
        
        # ScenarioConfigオブジェクトを作成
        scenario_type = self._get_scenario_type(scenario_name)
        
        return ScenarioConfig(
            scenario_type=scenario_type,
            concurrent_users=final_config.get("concurrent_users", 1),
            duration_minutes=final_config.get("duration_minutes", 5),
            ramp_up_seconds=final_config.get("ramp_up_seconds", 0),
            request_interval_min=final_config.get("request_interval_min", 1.0),
            request_interval_max=final_config.get("request_interval_max", 3.0),
            call_type=final_config.get("call_type", "direct"),
            include_trace_headers=final_config.get("include_trace_headers", True),
            timeout_seconds=final_config.get("timeout_seconds", 30),
            user_id_range=tuple(user_id_range),
            parameters=final_config.get("parameters")
        )
    
    def _get_scenario_type(self, scenario_name: str) -> ScenarioType:
        """シナリオ名からScenarioTypeを取得"""
        type_mapping = {
            "basic_distributed_tracing": ScenarioType.BASIC_DISTRIBUTED_TRACING,
            "n_plus_one_load_test": ScenarioType.N_PLUS_ONE_LOAD_TEST,
            "slow_query_load_test": ScenarioType.SLOW_QUERY_LOAD_TEST,
            "database_error_test": ScenarioType.DATABASE_ERROR_TEST,
            "concurrent_users_test": ScenarioType.CONCURRENT_USERS_TEST,
            "comprehensive_test": ScenarioType.COMPREHENSIVE_TEST
        }
        return type_mapping.get(scenario_name, ScenarioType.BASIC_DISTRIBUTED_TRACING)
    
    async def run_all_scenarios(self) -> Dict[str, ScenarioResult]:
        """全シナリオを順次実行"""
        if self.is_running:
            raise RuntimeError("Another scenario is already running")
        
        self.is_running = True
        
        try:
            logger.info("Starting all distributed service test scenarios")
            results = await self.runner.run_all_scenarios()
            logger.info("Completed all distributed service test scenarios")
            return results
        finally:
            self.is_running = False
    
    def stop_current_scenario(self):
        """現在実行中のシナリオを停止"""
        if self.is_running and self.current_scenario:
            self.scenarios.stop_all_scenarios()
            logger.info(f"Stopping current scenario: {self.current_scenario}")
    
    def get_scenario_results(self) -> List[Dict[str, Any]]:
        """シナリオ結果を取得"""
        results = self.scenarios.get_scenario_results()
        
        formatted_results = []
        for result in results:
            formatted_results.append({
                "scenario_type": result.scenario_type.value,
                "start_time": result.start_time.isoformat(),
                "end_time": result.end_time.isoformat() if result.end_time else None,
                "duration_seconds": result.duration_seconds,
                "total_requests": result.total_requests,
                "successful_requests": result.successful_requests,
                "failed_requests": result.failed_requests,
                "success_rate": result.success_rate,
                "average_response_time": result.average_response_time,
                "requests_per_second": result.requests_per_second,
                "errors": result.errors,
                "config": {
                    "concurrent_users": result.config.concurrent_users,
                    "duration_minutes": result.config.duration_minutes,
                    "call_type": result.config.call_type
                }
            })
        
        return formatted_results
    
    def get_latest_result(self, scenario_name: str) -> Optional[Dict[str, Any]]:
        """指定シナリオの最新結果を取得"""
        scenario_type = self._get_scenario_type(scenario_name)
        result = self.scenarios.get_latest_result(scenario_type)
        
        if result:
            return {
                "scenario_type": result.scenario_type.value,
                "start_time": result.start_time.isoformat(),
                "end_time": result.end_time.isoformat() if result.end_time else None,
                "duration_seconds": result.duration_seconds,
                "total_requests": result.total_requests,
                "successful_requests": result.successful_requests,
                "failed_requests": result.failed_requests,
                "success_rate": result.success_rate,
                "average_response_time": result.average_response_time,
                "requests_per_second": result.requests_per_second,
                "errors": result.errors
            }
        
        return None
    
    def generate_summary_report(self) -> Dict[str, Any]:
        """サマリーレポートを生成"""
        results = self.scenarios.get_scenario_results()
        
        if not results:
            return {
                "summary": {
                    "total_scenarios": 0,
                    "total_requests": 0,
                    "overall_success_rate": 0,
                    "average_response_time": 0
                },
                "scenarios": []
            }
        
        # 結果をScenarioResultからDict形式に変換
        results_dict = {}
        for result in results:
            results_dict[result.scenario_type.value] = result
        
        return self.runner.generate_summary_report(results_dict)
    
    def clear_results(self):
        """結果をクリア"""
        self.scenarios.clear_results()
        logger.info("Cleared all distributed service test results")
    
    def get_status(self) -> Dict[str, Any]:
        """現在のステータスを取得"""
        return {
            "is_running": self.is_running,
            "current_scenario": self.current_scenario,
            "total_results": len(self.scenarios.get_scenario_results()),
            "available_scenarios": len(self.get_available_scenarios())
        }
    
    def validate_configuration(self) -> Dict[str, Any]:
        """設定の検証"""
        validation_result = {
            "is_valid": True,
            "errors": [],
            "warnings": []
        }
        
        distributed_config = self.config.get("distributed_service")
        if not distributed_config:
            validation_result["is_valid"] = False
            validation_result["errors"].append("distributed_service configuration is missing")
            return validation_result
        
        # 必須設定の確認
        required_fields = ["base_url", "endpoints", "test_scenarios"]
        for field in required_fields:
            if field not in distributed_config:
                validation_result["is_valid"] = False
                validation_result["errors"].append(f"Required field '{field}' is missing in distributed_service config")
        
        # エンドポイント設定の確認
        endpoints = distributed_config.get("endpoints", {})
        required_endpoints = ["n-plus-one", "slow-query", "database-error"]
        for endpoint in required_endpoints:
            if endpoint not in endpoints:
                validation_result["warnings"].append(f"Endpoint '{endpoint}' is not configured")
        
        # テストシナリオ設定の確認
        test_scenarios = distributed_config.get("test_scenarios", {})
        if not test_scenarios:
            validation_result["warnings"].append("No test scenarios are configured")
        
        # メインアプリ設定の確認
        main_app_config = self.config.get("main_app_distributed")
        if not main_app_config:
            validation_result["warnings"].append("main_app_distributed configuration is missing - via_main_app tests will not work")
        
        return validation_result

# グローバルインスタンス
distributed_test_integration = DistributedTestIntegration()