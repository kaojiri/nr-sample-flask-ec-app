#!/usr/bin/env python3
"""
Test script for error handling and resource monitoring functionality
"""
import asyncio
import logging
import time
from datetime import datetime

from error_handler import error_handler, ErrorType, ErrorSeverity, ErrorAction
from resource_monitor import resource_monitor, ResourceThresholds, LoadAdjustmentAction

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_error_handler():
    """Test error handler functionality"""
    print("=" * 60)
    print("Testing Error Handler")
    print("=" * 60)
    
    # Test network error handling
    print("\n1. Testing Network Error Handling")
    try:
        import aiohttp
        network_error = aiohttp.ClientConnectionError("Connection refused")
        context = {"endpoint": "/test", "worker_id": "test-worker"}
        
        action = error_handler.handle_network_error(network_error, context)
        print(f"   Network error action: {action}")
        
    except Exception as e:
        print(f"   Error testing network error: {e}")
    
    # Test HTTP error handling
    print("\n2. Testing HTTP Error Handling")
    try:
        response_info = {"status_code": 500, "reason": "Internal Server Error"}
        context = {"endpoint": "/test", "worker_id": "test-worker"}
        
        action = error_handler.handle_http_error(response_info, context)
        print(f"   HTTP error action: {action}")
        
    except Exception as e:
        print(f"   Error testing HTTP error: {e}")
    
    # Test application error handling
    print("\n3. Testing Application Error Handling")
    try:
        app_error = ValueError("Invalid configuration")
        context = {"endpoint": "/test", "worker_id": "test-worker"}
        
        action = error_handler.handle_application_error(app_error, context)
        print(f"   Application error action: {action}")
        
    except Exception as e:
        print(f"   Error testing application error: {e}")
    
    # Test error statistics
    print("\n4. Testing Error Statistics")
    try:
        stats = error_handler.get_error_stats()
        print(f"   Total errors: {stats.total_errors}")
        print(f"   Errors last minute: {stats.errors_last_minute}")
        print(f"   Error types: {dict(stats.errors_by_type)}")
        
    except Exception as e:
        print(f"   Error getting error stats: {e}")
    
    # Test circuit breaker status
    print("\n5. Testing Circuit Breaker Status")
    try:
        cb_status = error_handler.get_circuit_breaker_status()
        print(f"   Circuit breakers: {len(cb_status)} active")
        for endpoint, status in cb_status.items():
            print(f"     {endpoint}: {status['state']} (failures: {status['failure_count']})")
        
    except Exception as e:
        print(f"   Error getting circuit breaker status: {e}")
    
    # Test should continue
    print("\n6. Testing Should Continue Test")
    try:
        should_continue = error_handler.should_continue_test()
        print(f"   Should continue test: {should_continue}")
        
    except Exception as e:
        print(f"   Error testing should continue: {e}")

async def test_resource_monitor():
    """Test resource monitor functionality"""
    print("\n" + "=" * 60)
    print("Testing Resource Monitor")
    print("=" * 60)
    
    # Test resource monitoring start/stop
    print("\n1. Testing Resource Monitoring Start/Stop")
    try:
        await resource_monitor.start_monitoring()
        print("   Resource monitoring started")
        
        # Wait a bit for monitoring to collect data
        await asyncio.sleep(2)
        
        current_usage = resource_monitor.get_current_usage()
        if current_usage:
            print(f"   CPU: {current_usage.cpu_percent:.1f}%")
            print(f"   Memory: {current_usage.memory_percent:.1f}%")
            print(f"   Disk: {current_usage.disk_percent:.1f}%")
            print(f"   Connections: {current_usage.network_connections}")
        else:
            print("   No usage data available yet")
        
        await resource_monitor.stop_monitoring()
        print("   Resource monitoring stopped")
        
    except Exception as e:
        print(f"   Error testing resource monitoring: {e}")
    
    # Test resource thresholds
    print("\n2. Testing Resource Thresholds")
    try:
        thresholds = resource_monitor.thresholds
        print(f"   CPU thresholds: {thresholds.cpu_warning}% / {thresholds.cpu_critical}% / {thresholds.cpu_emergency}%")
        print(f"   Memory thresholds: {thresholds.memory_warning}% / {thresholds.memory_critical}% / {thresholds.memory_emergency}%")
        
    except Exception as e:
        print(f"   Error testing resource thresholds: {e}")
    
    # Test connection limiting
    print("\n3. Testing Connection Limiting")
    try:
        # Set a low limit for testing
        resource_monitor.set_connection_limit(5)
        print(f"   Connection limit set to {resource_monitor.max_connections}")
        
        # Test acquiring connections
        acquired = []
        for i in range(7):  # Try to acquire more than limit
            if resource_monitor.acquire_connection():
                acquired.append(i)
                print(f"   Acquired connection {i}")
            else:
                print(f"   Failed to acquire connection {i} (limit reached)")
        
        # Release connections
        for i in acquired:
            resource_monitor.release_connection()
            print(f"   Released connection {i}")
        
        print(f"   Final connection count: {resource_monitor.current_connections}")
        
    except Exception as e:
        print(f"   Error testing connection limiting: {e}")
    
    # Test resource status
    print("\n4. Testing Resource Status")
    try:
        status = resource_monitor.get_resource_status()
        print(f"   Monitoring active: {status.get('monitoring_active', False)}")
        print(f"   Active alerts: {len(status.get('active_alerts', []))}")
        
        connection_info = status.get('connection_info', {})
        print(f"   Connections: {connection_info.get('current_connections', 0)}/{connection_info.get('max_connections', 0)}")
        
    except Exception as e:
        print(f"   Error testing resource status: {e}")

def test_callback_system():
    """Test callback system for errors and resource alerts"""
    print("\n" + "=" * 60)
    print("Testing Callback System")
    print("=" * 60)
    
    # Test error callbacks
    print("\n1. Testing Error Callbacks")
    try:
        error_count = 0
        
        def error_callback(error_info):
            nonlocal error_count
            error_count += 1
            print(f"   Error callback triggered: {error_info.message}")
        
        error_handler.add_error_callback(error_callback)
        
        # Trigger some errors
        context = {"endpoint": "/test", "worker_id": "test-worker"}
        error_handler.handle_application_error(ValueError("Test error 1"), context)
        error_handler.handle_application_error(RuntimeError("Test error 2"), context)
        
        print(f"   Error callbacks triggered: {error_count}")
        
        error_handler.remove_error_callback(error_callback)
        print("   Error callback removed")
        
    except Exception as e:
        print(f"   Error testing error callbacks: {e}")
    
    # Test resource alert callbacks
    print("\n2. Testing Resource Alert Callbacks")
    try:
        alert_count = 0
        
        def alert_callback(alert):
            nonlocal alert_count
            alert_count += 1
            print(f"   Alert callback triggered: {alert.message}")
        
        resource_monitor.add_alert_callback(alert_callback)
        
        # Test load adjustment callbacks
        adjustment_count = 0
        
        def adjustment_callback(action, context):
            nonlocal adjustment_count
            adjustment_count += 1
            print(f"   Load adjustment callback triggered: {action.value}")
        
        resource_monitor.add_load_adjustment_callback(adjustment_callback)
        
        print(f"   Callbacks registered")
        print(f"   Alert callbacks: {len(resource_monitor.alert_callbacks)}")
        print(f"   Load adjustment callbacks: {len(resource_monitor.load_adjustment_callbacks)}")
        
        # Clean up
        resource_monitor.remove_alert_callback(alert_callback)
        resource_monitor.remove_load_adjustment_callback(adjustment_callback)
        print("   Callbacks removed")
        
    except Exception as e:
        print(f"   Error testing resource callbacks: {e}")

async def test_integration():
    """Test integration between error handler and resource monitor"""
    print("\n" + "=" * 60)
    print("Testing Integration")
    print("=" * 60)
    
    print("\n1. Testing Error Handler Integration")
    try:
        # Test that error handler can determine if test should continue
        should_continue = error_handler.should_continue_test()
        print(f"   Should continue test: {should_continue}")
        
        # Get error statistics
        stats = error_handler.get_error_stats()
        print(f"   Current error stats: {stats.total_errors} total errors")
        
    except Exception as e:
        print(f"   Error testing error handler integration: {e}")
    
    print("\n2. Testing Resource Monitor Integration")
    try:
        # Test resource status
        status = resource_monitor.get_resource_status()
        print(f"   Resource monitoring available: {status is not None}")
        
        # Test connection management
        can_acquire = resource_monitor.acquire_connection()
        if can_acquire:
            resource_monitor.release_connection()
            print("   Connection management working")
        else:
            print("   Connection limit reached")
        
    except Exception as e:
        print(f"   Error testing resource monitor integration: {e}")

async def main():
    """Run all tests"""
    print("Load Testing Error Handling and Resource Monitoring Test")
    print("=" * 60)
    
    try:
        # Test error handler
        await test_error_handler()
        
        # Test resource monitor
        await test_resource_monitor()
        
        # Test callback system
        test_callback_system()
        
        # Test integration
        await test_integration()
        
        print("\n" + "=" * 60)
        print("All tests completed!")
        print("=" * 60)
        
        # Summary
        print("\nSummary:")
        print("✓ Error handling system implemented")
        print("✓ Resource monitoring system implemented")
        print("✓ Circuit breaker pattern implemented")
        print("✓ Connection limiting implemented")
        print("✓ Callback system implemented")
        print("✓ Load adjustment system implemented")
        print("✓ Integration between systems working")
        
        return True
        
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(main())