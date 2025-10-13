"""
Test script for endpoint selection and HTTP client functionality
"""
import asyncio
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from endpoint_selector import endpoint_selector, EndpointSelector
from http_client import AsyncHTTPClient, RequestStatus
from config import config_manager

async def test_endpoint_selection():
    """Test endpoint selection functionality"""
    print("Testing Endpoint Selection...")
    
    # Test endpoint loading
    print(f"Loaded {len(endpoint_selector.endpoints)} endpoints")
    
    # Test endpoint selection
    for i in range(5):
        selected = endpoint_selector.select_endpoint()
        if selected:
            print(f"Selection {i+1}: {selected.name} (weight: {selected.weight})")
        else:
            print(f"Selection {i+1}: No endpoint selected")
    
    # Test endpoint summary
    summary = endpoint_selector.get_endpoint_summary()
    print(f"\nEndpoint Summary:")
    print(f"Total endpoints: {summary['total_endpoints']}")
    print(f"Enabled endpoints: {summary['enabled_endpoints']}")
    
    for name, info in summary['endpoints'].items():
        print(f"  {name}: weight={info['weight']}, enabled={info['enabled']}")

async def test_http_client():
    """Test HTTP client functionality"""
    print("\nTesting HTTP Client...")
    
    async with AsyncHTTPClient() as client:
        # Test with a simple HTTP request (this will fail since target app isn't running)
        # but we can test the client functionality
        result = await client.make_get_request("http://httpbin.org/get", timeout=10)
        
        print(f"Request to httpbin.org:")
        print(f"  Status: {result.status.value}")
        print(f"  Status Code: {result.status_code}")
        print(f"  Response Time: {result.response_time:.3f}s")
        print(f"  Response Size: {result.response_size} bytes")
        print(f"  Success: {result.is_success}")
        
        if result.error_message:
            print(f"  Error: {result.error_message}")

async def test_integration():
    """Test integration between endpoint selector and HTTP client"""
    print("\nTesting Integration...")
    
    async with AsyncHTTPClient() as client:
        # Select an endpoint
        selected = endpoint_selector.select_endpoint()
        if selected:
            print(f"Selected endpoint: {selected.name}")
            print(f"URL: {selected.url}")
            
            # Try to make a request (will likely fail since target app isn't running)
            result = await client.make_request(selected.url, method=selected.method, timeout=5)
            
            print(f"Request result:")
            print(f"  Status: {result.status.value}")
            print(f"  Response Time: {result.response_time:.3f}s")
            
            # Update endpoint stats
            endpoint_selector.update_endpoint_stats(
                selected.name, 
                result.is_success, 
                result.response_time
            )
            
            # Check updated stats
            stats = endpoint_selector.get_endpoint_stats()
            endpoint_stats = stats.get(selected.name)
            if endpoint_stats:
                print(f"Updated stats for {selected.name}:")
                print(f"  Total requests: {endpoint_stats.total_requests}")
                print(f"  Success rate: {endpoint_stats.success_rate:.1f}%")

async def main():
    """Main test function"""
    print("Load Testing Automation - Endpoint Selection & HTTP Client Test")
    print("=" * 60)
    
    try:
        await test_endpoint_selection()
        await test_http_client()
        await test_integration()
        
        print("\n" + "=" * 60)
        print("All tests completed!")
        
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())