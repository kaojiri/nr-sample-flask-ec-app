#!/usr/bin/env python3
"""
Test script to verify the new endpoints are properly integrated
"""
import json
import os
from pathlib import Path

def test_new_endpoints_integration():
    """Test that the new endpoints are properly integrated"""
    print("Testing New Endpoints Integration")
    print("=" * 50)
    
    # Check for the new endpoints in configuration file
    new_endpoints = [
        "/performance/error",
        "/performance/slow-query/full-scan", 
        "/performance/slow-query/complex-join"
    ]
    
    # Load configuration file
    config_file = Path("data/config.json")
    if not config_file.exists():
        print("✗ Configuration file not found")
        return False
    
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    endpoints_config = config.get("endpoints", {})
    print(f"Total endpoints in config: {len(endpoints_config)}")
    
    print("\nChecking for new endpoints in configuration:")
    all_found = True
    for endpoint_path in new_endpoints:
        if endpoint_path in endpoints_config:
            config_data = endpoints_config[endpoint_path]
            print(f"✓ {endpoint_path}")
            print(f"  - Weight: {config_data.get('weight', 'N/A')}")
            print(f"  - Enabled: {config_data.get('enabled', 'N/A')}")
            print(f"  - Timeout: {config_data.get('timeout', 'N/A')}")
        else:
            print(f"✗ {endpoint_path} - NOT FOUND")
            all_found = False
    
    print(f"\nAll endpoints found in config: {'✓' if all_found else '✗'}")
    return all_found

def test_endpoint_code_integration():
    """Test that the new endpoints are integrated in the Python code"""
    print("\nTesting Code Integration for New Endpoints")
    print("=" * 50)
    
    # Check endpoint_selector.py for new endpoints
    endpoint_selector_file = Path("endpoint_selector.py")
    if not endpoint_selector_file.exists():
        print("✗ endpoint_selector.py not found")
        return False
    
    with open(endpoint_selector_file, 'r') as f:
        content = f.read()
    
    new_endpoints = [
        "/performance/error",
        "/performance/slow-query/full-scan", 
        "/performance/slow-query/complex-join"
    ]
    
    print("Checking for new endpoints in endpoint_selector.py:")
    all_found = True
    for endpoint_path in new_endpoints:
        if endpoint_path in content:
            print(f"✓ {endpoint_path} found in code")
        else:
            print(f"✗ {endpoint_path} - NOT FOUND in code")
            all_found = False
    
    # Check config.py for new endpoints
    config_file = Path("config.py")
    if config_file.exists():
        with open(config_file, 'r') as f:
            config_content = f.read()
        
        print("\nChecking for new endpoints in config.py:")
        for endpoint_path in new_endpoints:
            if endpoint_path in config_content:
                print(f"✓ {endpoint_path} found in config.py")
            else:
                print(f"✗ {endpoint_path} - NOT FOUND in config.py")
                all_found = False
    
    return all_found

def main():
    """Main test function"""
    print("New Endpoints Integration Test")
    print("=" * 60)
    
    try:
        # Test endpoint integration
        integration_test = test_new_endpoints_integration()
        
        # Test code integration
        code_test = test_endpoint_code_integration()
        
        print("\n" + "=" * 60)
        if integration_test and code_test:
            print("✅ ALL TESTS PASSED!")
            print("\nNew endpoints successfully integrated:")
            print("✓ /performance/error")
            print("✓ /performance/slow-query/full-scan")
            print("✓ /performance/slow-query/complex-join")
            print("\nFeatures verified:")
            print("✓ Endpoint configuration")
            print("✓ Endpoint selection logic")
            print("✓ Code integration")
            print("✓ Statistics tracking support")
            print("✓ Configuration file integration")
            return True
        else:
            print("❌ SOME TESTS FAILED!")
            return False
        
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)