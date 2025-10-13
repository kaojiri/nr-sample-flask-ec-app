#!/usr/bin/env python3
"""
Integration Test Runner for Load Testing Automation
Runs comprehensive integration tests for task 9.1
"""
import asyncio
import sys
import logging
import subprocess
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_basic_integration_tests():
    """Run basic integration tests"""
    logger.info("Running basic integration tests...")
    
    try:
        # Run pytest with verbose output
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            "test_integration_basic.py",
            "-v",
            "--tb=short",
            "--no-header"
        ], capture_output=True, text=True, cwd=Path(__file__).parent)
        
        print("=== BASIC INTEGRATION TEST RESULTS ===")
        print(result.stdout)
        
        if result.stderr:
            print("=== ERRORS ===")
            print(result.stderr)
        
        return result.returncode == 0
        
    except Exception as e:
        logger.error(f"Error running basic integration tests: {e}")
        return False

def test_load_test_start_stop():
    """Test load test start/stop functionality manually"""
    logger.info("Testing load test start/stop functionality...")
    
    try:
        from load_test_manager import LoadTestManager, LoadTestConfig
        from worker_pool import WorkerPool
        from unittest.mock import Mock, AsyncMock
        
        # Create mock worker pool
        worker_pool = Mock(spec=WorkerPool)
        worker_pool.start_workers = AsyncMock()
        worker_pool.stop_workers = AsyncMock()
        worker_pool.get_pool_stats = Mock(return_value={
            'total_requests': 10,
            'successful_requests': 8,
            'failed_requests': 2,
            'average_response_time': 1.5
        })
        worker_pool.set_statistics_callback = Mock()
        
        async def test_session():
            manager = LoadTestManager(worker_pool)
            
            # Test configuration
            config = LoadTestConfig(
                session_name="manual_test_session",
                concurrent_users=3,
                duration_minutes=1,
                request_interval_min=1.0,
                request_interval_max=2.0
            )
            
            # Start test
            session = await manager.start_test(config)
            logger.info(f"Started session: {session.id}")
            
            # Verify session started
            assert session.status.value == "running"
            assert session.start_time is not None
            
            # Wait a moment
            await asyncio.sleep(0.5)
            
            # Stop test
            success = await manager.stop_test(session.id)
            logger.info(f"Stopped session: {success}")
            
            # Verify session stopped
            final_session = manager.get_session(session.id)
            assert final_session.status.value == "completed"
            assert final_session.end_time is not None
            
            logger.info("✓ Load test start/stop test passed")
            return True
        
        return asyncio.run(test_session())
        
    except Exception as e:
        logger.error(f"Load test start/stop test failed: {e}")
        return False

def test_endpoint_access():
    """Test endpoint access functionality"""
    logger.info("Testing endpoint access functionality...")
    
    try:
        from endpoint_selector import EndpointSelector, EndpointConfig
        
        # Create endpoint selector with test endpoints
        selector = EndpointSelector()
        
        # Test endpoint selection
        selected = selector.select_endpoint()
        if selected:
            logger.info(f"✓ Selected endpoint: {selected.name} - {selected.url}")
        else:
            logger.warning("No endpoint selected")
        
        # Test endpoint statistics
        selector.record_request("slow", True, 1.5)
        selector.record_request("slow", False, 0.0)
        selector.record_request("n_plus_one", True, 2.3)
        
        stats = selector.get_endpoint_stats()
        if stats:
            logger.info(f"✓ Endpoint statistics collected: {len(stats)} endpoints")
            for name, stat in stats.items():
                logger.info(f"  {name}: {stat.total_requests} requests, {stat.success_rate:.1f}% success")
        
        logger.info("✓ Endpoint access test passed")
        return True
        
    except Exception as e:
        logger.error(f"Endpoint access test failed: {e}")
        return False

def test_error_handling():
    """Test error handling functionality"""
    logger.info("Testing error handling functionality...")
    
    try:
        from error_handler import ErrorHandler
        
        error_handler = ErrorHandler()
        
        # Test error handling
        test_errors = [
            (Exception("Network timeout"), "slow"),
            (Exception("Connection refused"), "n_plus_one"),
            (Exception("HTTP 500 error"), "slow_query"),
        ]
        
        for error, endpoint in test_errors:
            error_info = error_handler.handle_error(
                error, endpoint, f"http://test-app:5000/performance/{endpoint}"
            )
            logger.info(f"✓ Handled error for {endpoint}: {error_info.error_type}")
        
        # Test error statistics
        error_stats = error_handler.get_error_stats()
        logger.info(f"✓ Error statistics: {error_stats.total_errors} total errors")
        
        # Test circuit breaker
        cb_status = error_handler.get_circuit_breaker_status()
        logger.info(f"✓ Circuit breaker status: {len(cb_status)} endpoints monitored")
        
        logger.info("✓ Error handling test passed")
        return True
        
    except Exception as e:
        logger.error(f"Error handling test failed: {e}")
        return False

def test_configuration_management():
    """Test configuration management"""
    logger.info("Testing configuration management...")
    
    try:
        from config import ConfigManager
        
        config_manager = ConfigManager()
        
        # Test configuration update
        test_config = {
            "concurrent_users": 8,
            "duration_minutes": 15,
            "request_interval_min": 1.5,
            "request_interval_max": 3.0
        }
        
        success = config_manager.update_config(test_config)
        logger.info(f"✓ Configuration update: {success}")
        
        # Test configuration retrieval
        current_config = config_manager.get_config()
        logger.info(f"✓ Configuration retrieved: {len(current_config)} settings")
        
        # Verify values
        assert current_config["concurrent_users"] == 8
        assert current_config["duration_minutes"] == 15
        
        logger.info("✓ Configuration management test passed")
        return True
        
    except Exception as e:
        logger.error(f"Configuration management test failed: {e}")
        return False

def test_statistics_collection():
    """Test statistics collection"""
    logger.info("Testing statistics collection...")
    
    try:
        from statistics import StatisticsManager, StatisticsCollector
        
        stats_manager = StatisticsManager()
        
        # Create collector
        collector = stats_manager.create_collector("test_session")
        logger.info("✓ Statistics collector created")
        
        # Record some test data
        collector.record_request("slow", True, 1.5, 200)
        collector.record_request("n_plus_one", True, 2.3, 200)
        collector.record_request("slow_query", False, 0.0, 500)
        
        # Get statistics
        current_stats = collector.get_current_stats()
        logger.info(f"✓ Statistics collected: {current_stats.total_requests} requests")
        logger.info(f"  Success rate: {current_stats.success_rate:.1f}%")
        logger.info(f"  Average response time: {current_stats.average_response_time:.2f}s")
        
        # Cleanup
        asyncio.run(stats_manager.remove_collector("test_session"))
        
        logger.info("✓ Statistics collection test passed")
        return True
        
    except Exception as e:
        logger.error(f"Statistics collection test failed: {e}")
        return False

def main():
    """Run all integration tests"""
    logger.info("Starting Load Testing Integration Tests")
    logger.info("=" * 50)
    
    test_results = []
    
    # Run individual component tests
    tests = [
        ("Load Test Start/Stop", test_load_test_start_stop),
        ("Endpoint Access", test_endpoint_access),
        ("Error Handling", test_error_handling),
        ("Configuration Management", test_configuration_management),
        ("Statistics Collection", test_statistics_collection),
    ]
    
    for test_name, test_func in tests:
        logger.info(f"\n--- Running {test_name} Test ---")
        try:
            result = test_func()
            test_results.append((test_name, result))
            if result:
                logger.info(f"✓ {test_name} test PASSED")
            else:
                logger.error(f"✗ {test_name} test FAILED")
        except Exception as e:
            logger.error(f"✗ {test_name} test ERROR: {e}")
            test_results.append((test_name, False))
    
    # Run pytest-based tests
    logger.info(f"\n--- Running Pytest Integration Tests ---")
    pytest_result = run_basic_integration_tests()
    test_results.append(("Pytest Integration Tests", pytest_result))
    
    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("INTEGRATION TEST SUMMARY")
    logger.info("=" * 50)
    
    passed = 0
    failed = 0
    
    for test_name, result in test_results:
        status = "PASSED" if result else "FAILED"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    logger.info(f"\nTotal: {len(test_results)} tests")
    logger.info(f"Passed: {passed}")
    logger.info(f"Failed: {failed}")
    
    if failed == 0:
        logger.info("\n🎉 ALL INTEGRATION TESTS PASSED!")
        return 0
    else:
        logger.error(f"\n❌ {failed} INTEGRATION TESTS FAILED!")
        return 1

if __name__ == "__main__":
    sys.exit(main())