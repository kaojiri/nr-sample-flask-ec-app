"""
Integration Tests for Basic Load Testing Functionality
Tests for task 9.1: 基本機能の動作確認
- 負荷テストの開始・停止テスト
- 各エンドポイントへのアクセステスト  
- エラーハンドリングの確認
"""
import asyncio
import pytest
import json
import time
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from pathlib import Path

# Import components to test
from load_test_manager import LoadTestManager, LoadTestConfig, TestStatus
from worker_pool import WorkerPool
from endpoint_selector import EndpointSelector, EndpointConfig
from statistics import StatisticsManager
from error_handler import ErrorHandler
from http_client import HTTPClient
from config import ConfigManager

class TestBasicLoadTestFunctionality:
    """Test basic load testing functionality"""
    
    @pytest.fixture
    def setup_test_environment(self):
        """Setup test environment with mocked components"""
        # Create test data directory
        test_data_dir = Path("test_data")
        test_data_dir.mkdir(exist_ok=True)
        
        # Mock worker pool
        worker_pool = Mock(spec=WorkerPool)
        worker_pool.start_workers = AsyncMock()
        worker_pool.stop_workers = AsyncMock()
        worker_pool.emergency_stop = AsyncMock()
        worker_pool.get_pool_stats = Mock(return_value={
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'average_response_time': 0.0
        })
        worker_pool.set_statistics_callback = Mock()
        
        # Create load test manager
        manager = LoadTestManager(worker_pool)
        
        yield {
            'manager': manager,
            'worker_pool': worker_pool,
            'test_data_dir': test_data_dir
        }
        
        # Cleanup
        import shutil
        if test_data_dir.exists():
            shutil.rmtree(test_data_dir)
    
    @pytest.mark.asyncio
    async def test_load_test_start_stop_cycle(self, setup_test_environment):
        """Test complete load test start and stop cycle"""
        env = setup_test_environment
        manager = env['manager']
        worker_pool = env['worker_pool']
        
        # Create valid test configuration
        config = LoadTestConfig(
            session_name="integration_test_session",
            concurrent_users=5,
            duration_minutes=1,
            request_interval_min=1.0,
            request_interval_max=2.0
        )
        
        # Test session start
        session = await manager.start_test(config)
        
        assert session is not None
        assert session.config.session_name == "integration_test_session"
        assert session.status == TestStatus.RUNNING
        assert session.start_time is not None
        
        # Verify worker pool was started
        worker_pool.start_workers.assert_called_once()
        worker_pool.set_statistics_callback.assert_called_once()
        
        # Test session stop
        success = await manager.stop_test(session.id)
        
        assert success is True
        
        # Verify worker pool was stopped
        worker_pool.stop_workers.assert_called_once()
        
        # Check final session state
        final_session = manager.get_session(session.id)
        assert final_session.status == TestStatus.COMPLETED
        assert final_session.end_time is not None
    
    @pytest.mark.asyncio
    async def test_load_test_configuration_validation(self, setup_test_environment):
        """Test load test configuration validation"""
        env = setup_test_environment
        manager = env['manager']
        
        # Test invalid configurations
        invalid_configs = [
            # Empty session name
            LoadTestConfig(session_name="", concurrent_users=5),
            # Too many concurrent users
            LoadTestConfig(session_name="test", concurrent_users=100),
            # Invalid duration
            LoadTestConfig(session_name="test", concurrent_users=5, duration_minutes=0),
            # Invalid request intervals
            LoadTestConfig(session_name="test", concurrent_users=5, 
                         request_interval_min=2.0, request_interval_max=1.0),
        ]
        
        for config in invalid_configs:
            with pytest.raises(ValueError):
                await manager.start_test(config)
    
    @pytest.mark.asyncio
    async def test_emergency_stop_functionality(self, setup_test_environment):
        """Test emergency stop functionality"""
        env = setup_test_environment
        manager = env['manager']
        worker_pool = env['worker_pool']
        
        # Start a test session
        config = LoadTestConfig(
            session_name="emergency_test_session",
            concurrent_users=3,
            duration_minutes=10  # Long duration
        )
        
        session = await manager.start_test(config)
        assert session.status == TestStatus.RUNNING
        
        # Trigger emergency stop
        success = await manager.emergency_stop()
        
        assert success is True
        worker_pool.emergency_stop.assert_called_once()
        
        # Check session was cancelled
        final_session = manager.get_session(session.id)
        assert final_session.status == TestStatus.CANCELLED
        assert "Emergency stop" in final_session.error_message
    
    @pytest.mark.asyncio
    async def test_concurrent_session_prevention(self, setup_test_environment):
        """Test that only one session can run at a time"""
        env = setup_test_environment
        manager = env['manager']
        
        # Start first session
        config1 = LoadTestConfig(
            session_name="session_1",
            concurrent_users=3,
            duration_minutes=5
        )
        
        session1 = await manager.start_test(config1)
        assert session1.status == TestStatus.RUNNING
        
        # Try to start second session - should fail
        config2 = LoadTestConfig(
            session_name="session_2",
            concurrent_users=2,
            duration_minutes=3
        )
        
        with pytest.raises(ValueError, match="Another test session is already running"):
            await manager.start_test(config2)
        
        # Stop first session
        await manager.stop_test(session1.id)
        
        # Now second session should start successfully
        session2 = await manager.start_test(config2)
        assert session2.status == TestStatus.RUNNING
        
        await manager.stop_test(session2.id)

class TestEndpointAccessFunctionality:
    """Test endpoint access functionality"""
    
    @pytest.fixture
    def setup_endpoint_test(self):
        """Setup endpoint testing environment"""
        # Mock HTTP client
        http_client = Mock(spec=HTTPClient)
        
        # Create endpoint selector with test endpoints
        test_endpoints = {
            "slow": EndpointConfig(
                name="slow",
                url="http://test-app:5000/performance/slow",
                method="GET",
                weight=1.0,
                description="Slow processing endpoint"
            ),
            "n_plus_one": EndpointConfig(
                name="n_plus_one", 
                url="http://test-app:5000/performance/n-plus-one",
                method="GET",
                weight=1.0,
                description="N+1 query problem endpoint"
            ),
            "slow_query": EndpointConfig(
                name="slow_query",
                url="http://test-app:5000/performance/slow-query", 
                method="GET",
                weight=1.0,
                description="Slow database query endpoint"
            ),
            "js_errors": EndpointConfig(
                name="js_errors",
                url="http://test-app:5000/performance/js-errors",
                method="GET", 
                weight=1.0,
                description="JavaScript errors endpoint"
            ),
            "bad_vitals": EndpointConfig(
                name="bad_vitals",
                url="http://test-app:5000/performance/bad-vitals",
                method="GET",
                weight=1.0,
                description="Bad Core Web Vitals endpoint"
            )
        }
        
        endpoint_selector = EndpointSelector()
        endpoint_selector.endpoints = test_endpoints
        
        yield {
            'http_client': http_client,
            'endpoint_selector': endpoint_selector,
            'test_endpoints': test_endpoints
        }
    
    def test_endpoint_selection_logic(self, setup_endpoint_test):
        """Test endpoint selection with different weights"""
        env = setup_endpoint_test
        endpoint_selector = env['endpoint_selector']
        
        # Test basic selection
        selected = endpoint_selector.select_endpoint()
        assert selected is not None
        assert selected.name in env['test_endpoints']
        
        # Test weighted selection
        weights = {
            "slow": 2.0,
            "n_plus_one": 1.0,
            "slow_query": 3.0,
            "js_errors": 0.5,
            "bad_vitals": 1.5
        }
        
        endpoint_selector.update_weights(weights)
        
        # Select multiple times to test distribution
        selections = {}
        for _ in range(100):
            selected = endpoint_selector.select_endpoint()
            selections[selected.name] = selections.get(selected.name, 0) + 1
        
        # Verify all endpoints were selected
        assert len(selections) > 0
        
        # Higher weight endpoints should be selected more often
        assert selections.get("slow_query", 0) > selections.get("js_errors", 0)
    
    def test_endpoint_statistics_tracking(self, setup_endpoint_test):
        """Test endpoint statistics tracking"""
        env = setup_endpoint_test
        endpoint_selector = env['endpoint_selector']
        
        # Simulate requests to different endpoints
        test_data = [
            ("slow", True, 1.5),
            ("slow", False, 0.0),
            ("n_plus_one", True, 2.3),
            ("slow_query", True, 3.1),
            ("js_errors", False, 0.0),
        ]
        
        for endpoint_name, success, response_time in test_data:
            endpoint_selector.record_request(endpoint_name, success, response_time)
        
        # Check statistics
        stats = endpoint_selector.get_endpoint_stats()
        
        # Verify slow endpoint stats
        slow_stats = stats.get("slow")
        assert slow_stats is not None
        assert slow_stats.total_requests == 2
        assert slow_stats.successful_requests == 1
        assert slow_stats.failed_requests == 1
        assert slow_stats.success_rate == 50.0
        
        # Verify n_plus_one endpoint stats
        n_plus_one_stats = stats.get("n_plus_one")
        assert n_plus_one_stats is not None
        assert n_plus_one_stats.total_requests == 1
        assert n_plus_one_stats.successful_requests == 1
        assert n_plus_one_stats.success_rate == 100.0
    
    @pytest.mark.asyncio
    async def test_endpoint_access_with_http_client(self, setup_endpoint_test):
        """Test actual endpoint access through HTTP client"""
        env = setup_endpoint_test
        http_client = env['http_client']
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="Success")
        mock_response.headers = {"Content-Type": "text/html"}
        
        http_client.make_request = AsyncMock(return_value=(mock_response, 1.23))
        
        # Test request to each endpoint
        for endpoint_name, endpoint_config in env['test_endpoints'].items():
            response, response_time = await http_client.make_request(
                endpoint_config.url,
                method=endpoint_config.method,
                timeout=30
            )
            
            assert response.status == 200
            assert response_time > 0
            
        # Verify all requests were made
        assert http_client.make_request.call_count == len(env['test_endpoints'])

class TestErrorHandlingFunctionality:
    """Test error handling functionality"""
    
    @pytest.fixture
    def setup_error_test(self):
        """Setup error handling test environment"""
        error_handler = ErrorHandler()
        
        # Mock HTTP client for error scenarios
        http_client = Mock(spec=HTTPClient)
        
        yield {
            'error_handler': error_handler,
            'http_client': http_client
        }
    
    @pytest.mark.asyncio
    async def test_network_error_handling(self, setup_error_test):
        """Test network error handling"""
        env = setup_error_test
        http_client = env['http_client']
        error_handler = env['error_handler']
        
        # Mock network timeout error
        import aiohttp
        http_client.make_request = AsyncMock(
            side_effect=aiohttp.ClientTimeout("Request timeout")
        )
        
        # Test error handling
        try:
            await http_client.make_request("http://test-app:5000/performance/slow")
        except Exception as e:
            error_info = error_handler.handle_error(e, "slow", "http://test-app:5000/performance/slow")
            
            assert error_info is not None
            assert error_info.error_type == "network_error"
            assert "timeout" in error_info.message.lower()
    
    @pytest.mark.asyncio
    async def test_http_error_handling(self, setup_error_test):
        """Test HTTP error response handling"""
        env = setup_error_test
        http_client = env['http_client']
        error_handler = env['error_handler']
        
        # Mock HTTP 500 error response
        mock_response = Mock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Internal Server Error")
        mock_response.reason = "Internal Server Error"
        
        http_client.make_request = AsyncMock(return_value=(mock_response, 0.5))
        
        # Test error handling
        response, response_time = await http_client.make_request("http://test-app:5000/performance/slow")
        
        if response.status >= 400:
            error_info = error_handler.handle_http_error(response, "slow", "http://test-app:5000/performance/slow")
            
            assert error_info is not None
            assert error_info.error_type == "http_error"
            assert error_info.status_code == 500
    
    def test_circuit_breaker_functionality(self, setup_error_test):
        """Test circuit breaker functionality"""
        env = setup_error_test
        error_handler = env['error_handler']
        
        endpoint_name = "slow"
        
        # Simulate multiple failures to trigger circuit breaker
        for _ in range(10):  # Exceed failure threshold
            error_info = error_handler.handle_error(
                Exception("Simulated error"), 
                endpoint_name, 
                "http://test-app:5000/performance/slow"
            )
        
        # Check circuit breaker status
        cb_status = error_handler.get_circuit_breaker_status()
        
        # Circuit breaker should be open for this endpoint
        assert endpoint_name in cb_status
        endpoint_cb = cb_status[endpoint_name]
        assert endpoint_cb['state'] in ['open', 'half_open']
        assert endpoint_cb['failure_count'] >= 5
    
    def test_error_statistics_collection(self, setup_error_test):
        """Test error statistics collection"""
        env = setup_error_test
        error_handler = env['error_handler']
        
        # Simulate various errors
        test_errors = [
            (Exception("Network timeout"), "slow"),
            (Exception("Connection refused"), "n_plus_one"),
            (Exception("DNS resolution failed"), "slow_query"),
            (Exception("SSL certificate error"), "js_errors"),
        ]
        
        for error, endpoint in test_errors:
            error_handler.handle_error(error, endpoint, f"http://test-app:5000/performance/{endpoint}")
        
        # Check error statistics
        error_stats = error_handler.get_error_stats()
        
        assert error_stats.total_errors >= len(test_errors)
        assert len(error_stats.error_by_endpoint) > 0
        assert len(error_stats.error_by_type) > 0
        
        # Check recent errors
        recent_errors = error_handler.get_recent_errors(10)
        assert len(recent_errors) >= len(test_errors)

class TestIntegrationWithRealComponents:
    """Integration tests with real components (mocked external dependencies)"""
    
    @pytest.mark.asyncio
    async def test_full_load_test_simulation(self):
        """Test full load test simulation with mocked HTTP responses"""
        
        # Setup real components
        from worker_pool import WorkerPool
        from statistics import StatisticsManager
        
        worker_pool = WorkerPool()
        statistics_manager = StatisticsManager()
        manager = LoadTestManager(worker_pool)
        
        # Mock HTTP client to simulate responses
        with patch('http_client.HTTPClient.make_request') as mock_request:
            # Setup mock responses for different endpoints
            def mock_response_generator(url, **kwargs):
                mock_response = Mock()
                if "slow" in url:
                    mock_response.status = 200
                    response_time = 2.0  # Slow response
                elif "n-plus-one" in url:
                    mock_response.status = 200
                    response_time = 1.5
                elif "js-errors" in url:
                    mock_response.status = 500  # Error response
                    response_time = 0.5
                else:
                    mock_response.status = 200
                    response_time = 1.0
                
                mock_response.text = AsyncMock(return_value="Response body")
                return asyncio.create_task(asyncio.coroutine(lambda: (mock_response, response_time))())
            
            mock_request.side_effect = mock_response_generator
            
            # Start load test
            config = LoadTestConfig(
                session_name="full_simulation_test",
                concurrent_users=3,
                duration_minutes=1,  # Short duration for test
                request_interval_min=0.5,
                request_interval_max=1.0
            )
            
            session = await manager.start_test(config)
            
            # Let it run for a short time
            await asyncio.sleep(2.0)
            
            # Stop the test
            success = await manager.stop_test(session.id)
            assert success is True
            
            # Verify session completed
            final_session = manager.get_session(session.id)
            assert final_session.status == TestStatus.COMPLETED
            
            # Verify some requests were made
            assert mock_request.call_count > 0
    
    def test_configuration_persistence(self):
        """Test configuration persistence across restarts"""
        
        # Create test configuration
        config_manager = ConfigManager()
        
        test_config = {
            "concurrent_users": 15,
            "duration_minutes": 45,
            "request_interval_min": 2.0,
            "request_interval_max": 4.0,
            "endpoint_weights": {
                "slow": 2.0,
                "n_plus_one": 1.5
            }
        }
        
        # Save configuration
        success = config_manager.update_config(test_config)
        assert success is True
        
        # Create new config manager instance (simulate restart)
        new_config_manager = ConfigManager()
        loaded_config = new_config_manager.get_config()
        
        # Verify configuration was persisted
        assert loaded_config["concurrent_users"] == 15
        assert loaded_config["duration_minutes"] == 45
        assert loaded_config["endpoint_weights"]["slow"] == 2.0

if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])