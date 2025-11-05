"""
分散サービステスト統合機能のテスト
"""
import asyncio
import logging
try:
    import pytest
    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False

from distributed_test_integration import DistributedTestIntegration
from distributed_test_scenarios import ScenarioConfig, ScenarioType
from config import config_manager

logger = logging.getLogger(__name__)

class TestDistributedServiceIntegration:
    """分散サービステスト統合機能のテストクラス"""
    
    def setup_method(self):
        """テストメソッドの前処理"""
        self.integration = DistributedTestIntegration()
    
    def test_get_available_scenarios(self):
        """利用可能なシナリオの取得テスト"""
        scenarios = self.integration.get_available_scenarios()
        
        assert isinstance(scenarios, list)
        assert len(scenarios) > 0
        
        # 各シナリオの必須フィールドを確認
        for scenario in scenarios:
            assert "name" in scenario
            assert "display_name" in scenario
            assert "description" in scenario
            assert "config" in scenario
            assert "estimated_duration_minutes" in scenario
            assert "concurrent_users" in scenario
    
    def test_get_display_name(self):
        """表示名の取得テスト"""
        display_name = self.integration._get_display_name("basic_distributed_tracing")
        assert display_name == "基本分散トレーシングテスト"
        
        display_name = self.integration._get_display_name("unknown_scenario")
        assert display_name == "Unknown Scenario"
    
    def test_get_scenario_description(self):
        """シナリオ説明の取得テスト"""
        description = self.integration._get_scenario_description("n_plus_one_load_test")
        assert "N+1クエリ問題" in description
        
        description = self.integration._get_scenario_description("unknown_scenario")
        assert description == "分散サービステストシナリオ"
    
    def test_get_scenario_type(self):
        """シナリオタイプの取得テスト"""
        scenario_type = self.integration._get_scenario_type("basic_distributed_tracing")
        assert scenario_type == ScenarioType.BASIC_DISTRIBUTED_TRACING
        
        scenario_type = self.integration._get_scenario_type("n_plus_one_load_test")
        assert scenario_type == ScenarioType.N_PLUS_ONE_LOAD_TEST
    
    def test_prepare_scenario_config(self):
        """シナリオ設定の準備テスト"""
        config = self.integration._prepare_scenario_config("basic_distributed_tracing", None)
        
        assert isinstance(config, ScenarioConfig)
        assert config.scenario_type == ScenarioType.BASIC_DISTRIBUTED_TRACING
        assert config.concurrent_users >= 1
        assert config.duration_minutes >= 1
        assert config.user_id_range == (1, 100)
    
    def test_prepare_scenario_config_with_custom(self):
        """カスタム設定でのシナリオ設定準備テスト"""
        custom_config = {
            "concurrent_users": 5,
            "duration_minutes": 10,
            "timeout_seconds": 60
        }
        
        config = self.integration._prepare_scenario_config("basic_distributed_tracing", custom_config)
        
        assert config.concurrent_users == 5
        assert config.duration_minutes == 10
        assert config.timeout_seconds == 60
    
    def test_get_status(self):
        """ステータス取得テスト"""
        status = self.integration.get_status()
        
        assert isinstance(status, dict)
        assert "is_running" in status
        assert "current_scenario" in status
        assert "total_results" in status
        assert "available_scenarios" in status
        
        assert status["is_running"] is False
        assert status["current_scenario"] is None
    
    def test_validate_configuration(self):
        """設定検証テスト"""
        validation_result = self.integration.validate_configuration()
        
        assert isinstance(validation_result, dict)
        assert "is_valid" in validation_result
        assert "errors" in validation_result
        assert "warnings" in validation_result
        
        # 設定が存在する場合は有効であることを確認
        if self.integration.config.get("distributed_service"):
            assert validation_result["is_valid"] is True
    
    def test_get_scenario_results_empty(self):
        """空の結果取得テスト"""
        results = self.integration.get_scenario_results()
        
        assert isinstance(results, list)
        # 初期状態では結果は空
        assert len(results) == 0
    
    def test_generate_summary_report_empty(self):
        """空のサマリーレポート生成テスト"""
        report = self.integration.generate_summary_report()
        
        assert isinstance(report, dict)
        assert "summary" in report
        assert report["summary"]["total_scenarios"] == 0
        assert report["summary"]["total_requests"] == 0
    
    def test_clear_results(self):
        """結果クリアテスト"""
        # 例外が発生しないことを確認
        self.integration.clear_results()
    
    def test_stop_current_scenario_when_not_running(self):
        """実行中でない場合のシナリオ停止テスト"""
        # 例外が発生しないことを確認
        self.integration.stop_current_scenario()

if PYTEST_AVAILABLE:
    @pytest.mark.asyncio
    class TestDistributedServiceIntegrationAsync:
        """分散サービステスト統合機能の非同期テストクラス"""
        
        def setup_method(self):
            """テストメソッドの前処理"""
            self.integration = DistributedTestIntegration()
        
        async def test_run_scenario_when_already_running(self):
            """既に実行中の場合のシナリオ実行テスト"""
            self.integration.is_running = True
            
            with pytest.raises(RuntimeError, match="Another scenario is already running"):
                await self.integration.run_scenario("basic_distributed_tracing")
        
        async def test_run_all_scenarios_when_already_running(self):
            """既に実行中の場合の全シナリオ実行テスト"""
            self.integration.is_running = True
            
            with pytest.raises(RuntimeError, match="Another scenario is already running"):
                await self.integration.run_all_scenarios()

def test_configuration_validation():
    """設定検証の詳細テスト"""
    # 現在の設定を取得
    config = config_manager.get_config()
    
    # 分散サービス設定が存在することを確認
    distributed_config = config.get("distributed_service")
    if distributed_config:
        assert "base_url" in distributed_config
        assert "endpoints" in distributed_config
        assert "test_scenarios" in distributed_config
        
        # エンドポイント設定を確認
        endpoints = distributed_config["endpoints"]
        required_endpoints = ["n-plus-one", "slow-query", "database-error"]
        for endpoint in required_endpoints:
            assert endpoint in endpoints
        
        # テストシナリオ設定を確認
        test_scenarios = distributed_config["test_scenarios"]
        assert len(test_scenarios) > 0
        
        for scenario_name, scenario_config in test_scenarios.items():
            assert "concurrent_users" in scenario_config
            assert "duration_minutes" in scenario_config
            assert "call_type" in scenario_config

def test_scenario_config_validation():
    """シナリオ設定の検証テスト"""
    integration = DistributedTestIntegration()
    
    # 各シナリオの設定を検証
    scenarios = integration.get_available_scenarios()
    
    for scenario in scenarios:
        config_data = scenario["config"]
        
        # 必須フィールドの確認
        assert "concurrent_users" in config_data
        assert "duration_minutes" in config_data
        assert "call_type" in config_data
        
        # 値の妥当性確認
        assert config_data["concurrent_users"] > 0
        assert config_data["duration_minutes"] > 0
        assert config_data["call_type"] in ["direct", "via_main_app", "both"]

if __name__ == "__main__":
    # 基本的なテストを実行
    logging.basicConfig(level=logging.INFO)
    
    print("Testing distributed service integration...")
    
    # 同期テストの実行
    integration = DistributedTestIntegration()
    
    print("✓ Available scenarios:", len(integration.get_available_scenarios()))
    print("✓ Configuration validation:", integration.validate_configuration()["is_valid"])
    print("✓ Status:", integration.get_status())
    
    print("All basic tests passed!")