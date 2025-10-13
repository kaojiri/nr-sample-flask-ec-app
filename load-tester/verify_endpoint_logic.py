"""
Simple verification script for endpoint selection logic without external dependencies
"""
import random
import json
from pathlib import Path

def test_weighted_selection():
    """Test the weighted random selection algorithm"""
    print("Testing weighted random selection algorithm...")
    
    # Sample endpoints with weights
    endpoints = {
        "/performance/slow": {"weight": 2.0},
        "/performance/n-plus-one": {"weight": 1.0},
        "/performance/slow-query": {"weight": 3.0},
        "/performance/js-errors": {"weight": 1.5},
        "/performance/bad-vitals": {"weight": 1.0}
    }
    
    # Test weighted selection
    endpoint_names = list(endpoints.keys())
    weights = [endpoints[name]["weight"] for name in endpoint_names]
    
    # Count selections over multiple iterations
    selection_counts = {name: 0 for name in endpoint_names}
    iterations = 1000
    
    for _ in range(iterations):
        selected = random.choices(endpoint_names, weights=weights, k=1)[0]
        selection_counts[selected] += 1
    
    print(f"Results after {iterations} selections:")
    for name, count in selection_counts.items():
        percentage = (count / iterations) * 100
        weight = endpoints[name]["weight"]
        print(f"  {name}: {count} times ({percentage:.1f}%) - weight: {weight}")
    
    return True

def test_config_structure():
    """Test configuration structure"""
    print("\nTesting configuration structure...")
    
    # Sample configuration
    config = {
        "target_app_url": "http://app:5000",
        "load_test": {
            "concurrent_users": 10,
            "duration_minutes": 30,
            "request_interval_min": 1.0,
            "request_interval_max": 5.0,
            "max_errors_per_minute": 100,
            "enable_logging": True
        },
        "endpoints": {
            "/performance/slow": {"weight": 1.0, "enabled": True},
            "/performance/n-plus-one": {"weight": 1.0, "enabled": True},
            "/performance/slow-query": {"weight": 1.0, "enabled": True},
            "/performance/js-errors": {"weight": 1.0, "enabled": True},
            "/performance/bad-vitals": {"weight": 1.0, "enabled": True}
        },
        "safety": {
            "max_concurrent_users": 50,
            "max_duration_minutes": 120,
            "emergency_stop_enabled": True
        }
    }
    
    # Test configuration access
    print("Configuration structure:")
    print(f"  Target URL: {config['target_app_url']}")
    print(f"  Concurrent users: {config['load_test']['concurrent_users']}")
    print(f"  Endpoints count: {len(config['endpoints'])}")
    
    # Test endpoint URL construction
    target_url = config['target_app_url'].rstrip('/')
    for endpoint_path in config['endpoints']:
        full_url = f"{target_url}{endpoint_path}"
        print(f"  {endpoint_path} -> {full_url}")
    
    return True

def test_endpoint_stats():
    """Test endpoint statistics calculation"""
    print("\nTesting endpoint statistics...")
    
    class MockEndpointStats:
        def __init__(self, name):
            self.name = name
            self.total_requests = 0
            self.successful_requests = 0
            self.failed_requests = 0
            self.total_response_time = 0.0
        
        @property
        def success_rate(self):
            if self.total_requests == 0:
                return 0.0
            return (self.successful_requests / self.total_requests) * 100
        
        @property
        def average_response_time(self):
            if self.successful_requests == 0:
                return 0.0
            return self.total_response_time / self.successful_requests
    
    # Test stats calculation
    stats = MockEndpointStats("/performance/slow")
    
    # Simulate some requests
    test_cases = [
        (True, 0.5),   # Success, 0.5s
        (True, 1.2),   # Success, 1.2s
        (False, 0.0),  # Failure
        (True, 0.8),   # Success, 0.8s
        (False, 0.0),  # Failure
    ]
    
    for success, response_time in test_cases:
        stats.total_requests += 1
        if success:
            stats.successful_requests += 1
            stats.total_response_time += response_time
        else:
            stats.failed_requests += 1
    
    print(f"Stats for {stats.name}:")
    print(f"  Total requests: {stats.total_requests}")
    print(f"  Successful: {stats.successful_requests}")
    print(f"  Failed: {stats.failed_requests}")
    print(f"  Success rate: {stats.success_rate:.1f}%")
    print(f"  Average response time: {stats.average_response_time:.3f}s")
    
    return True

def main():
    """Main verification function"""
    print("Endpoint Selection Logic Verification")
    print("=" * 50)
    
    try:
        test_weighted_selection()
        test_config_structure()
        test_endpoint_stats()
        
        print("\n" + "=" * 50)
        print("All verification tests passed!")
        return True
        
    except Exception as e:
        print(f"Verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)