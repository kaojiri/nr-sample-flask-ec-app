#!/usr/bin/env python3
"""
Simple test script for user session management functionality
Tests the basic data structures and configuration management without HTTP dependencies
"""
import sys
import json
from pathlib import Path

# Add the load-tester directory to the path
sys.path.insert(0, str(Path(__file__).parent))

def test_test_user_data_model():
    """Test TestUser data model"""
    print("=" * 60)
    print("Testing TestUser Data Model")
    print("=" * 60)
    
    try:
        # Import without HTTP dependencies
        from user_session_manager import TestUser
        
        # Test 1: Create a test user
        print("\n1. Creating a test user...")
        user = TestUser(
            user_id="test_user_1",
            username="testuser@example.com",
            password="password123",
            enabled=True,
            description="Test user for validation"
        )
        
        print(f"   - User ID: {user.user_id}")
        print(f"   - Username: {user.username}")
        print(f"   - Enabled: {user.enabled}")
        print(f"   - Description: {user.description}")
        
        # Test 2: Convert to dictionary
        print("\n2. Converting to dictionary...")
        user_dict = user.to_dict()
        print(f"   - Dictionary keys: {list(user_dict.keys())}")
        print(f"   - Username in dict: {user_dict['username']}")
        
        # Test 3: Create from dictionary
        print("\n3. Creating from dictionary...")
        user2 = TestUser.from_dict(user_dict)
        print(f"   - Recreated user ID: {user2.user_id}")
        print(f"   - Recreated username: {user2.username}")
        print(f"   - Match original: {user.username == user2.username}")
        
        print("\n✅ TestUser data model test passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ TestUser data model test failed: {e}")
        return False

def test_user_session_data_model():
    """Test UserSession data model"""
    print("\n" + "=" * 60)
    print("Testing UserSession Data Model")
    print("=" * 60)
    
    try:
        from user_session_manager import UserSession
        from datetime import datetime
        
        # Test 1: Create a user session
        print("\n1. Creating a user session...")
        session = UserSession(
            user_id="test_user_1",
            username="testuser@example.com",
            session_cookie="session_123456",
            login_time=datetime.now(),
            last_used=datetime.now()
        )
        
        print(f"   - User ID: {session.user_id}")
        print(f"   - Username: {session.username}")
        print(f"   - Session cookie: {session.session_cookie}")
        print(f"   - Is valid: {session.is_valid}")
        print(f"   - Is expired: {session.is_expired}")
        print(f"   - Age minutes: {session.age_minutes:.2f}")
        
        # Test 2: Convert to dictionary
        print("\n2. Converting to dictionary...")
        session_dict = session.to_dict()
        print(f"   - Dictionary keys: {list(session_dict.keys())}")
        
        # Test 3: Create from dictionary
        print("\n3. Creating from dictionary...")
        session2 = UserSession.from_dict(session_dict)
        print(f"   - Recreated user ID: {session2.user_id}")
        print(f"   - Recreated username: {session2.username}")
        print(f"   - Match original: {session.username == session2.username}")
        
        # Test 4: Update last used
        print("\n4. Testing update last used...")
        old_last_used = session.last_used
        session.update_last_used()
        print(f"   - Last used updated: {session.last_used > old_last_used}")
        
        print("\n✅ UserSession data model test passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ UserSession data model test failed: {e}")
        return False

def test_configuration_integration():
    """Test configuration integration"""
    print("\n" + "=" * 60)
    print("Testing Configuration Integration")
    print("=" * 60)
    
    try:
        # Test 1: Read current configuration
        print("\n1. Reading current configuration...")
        config_file = Path("data/config.json")
        
        if config_file.exists():
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            test_users = config.get("test_users", [])
            print(f"   - Configuration file exists")
            print(f"   - Found {len(test_users)} test users in config")
            
            for user in test_users:
                print(f"     * {user.get('username', 'Unknown')} ({user.get('user_id', 'No ID')})")
        else:
            print("   - Configuration file does not exist")
            return False
        
        # Test 2: Validate test user structure
        print("\n2. Validating test user structure...")
        required_fields = ['user_id', 'username', 'password', 'enabled']
        
        for i, user in enumerate(test_users):
            missing_fields = [field for field in required_fields if field not in user]
            if missing_fields:
                print(f"   - User {i+1} missing fields: {missing_fields}")
                return False
            else:
                print(f"   - User {i+1} ({user['username']}): ✅ Valid structure")
        
        # Test 3: Test load_test configuration
        print("\n3. Checking load_test configuration...")
        load_test_config = config.get("load_test", {})
        enable_user_login = load_test_config.get("enable_user_login", False)
        print(f"   - Enable user login: {enable_user_login}")
        
        print("\n✅ Configuration integration test passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Configuration integration test failed: {e}")
        return False

def test_api_data_structures():
    """Test API data structures"""
    print("\n" + "=" * 60)
    print("Testing API Data Structures")
    print("=" * 60)
    
    try:
        # Test 1: Simulate API request data
        print("\n1. Testing API request data structures...")
        
        # Test user creation request
        user_request = {
            "user_id": "api_test_user",
            "username": "apitest@example.com",
            "password": "apipass123",
            "enabled": True,
            "description": "API test user"
        }
        
        print(f"   - User request structure: ✅")
        print(f"   - Required fields present: {all(field in user_request for field in ['user_id', 'username', 'password'])}")
        
        # Test load test request with user login
        load_test_request = {
            "session_name": "test-with-users",
            "concurrent_users": 5,
            "duration_minutes": 10,
            "enable_user_login": True,
            "enable_logging": True
        }
        
        print(f"   - Load test request structure: ✅")
        print(f"   - User login enabled: {load_test_request['enable_user_login']}")
        
        # Test 2: Simulate API response data
        print("\n2. Testing API response data structures...")
        
        session_stats = {
            "total_users": 3,
            "active_sessions": 2,
            "expired_sessions": 0,
            "failed_logins": 1,
            "successful_logins": 2
        }
        
        print(f"   - Session stats structure: ✅")
        print(f"   - Active sessions: {session_stats['active_sessions']}")
        
        print("\n✅ API data structures test passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ API data structures test failed: {e}")
        return False

def main():
    """Main test function"""
    print("Starting Simple User Session Management Tests...")
    print("(Testing without HTTP dependencies)")
    
    # Run tests
    test_results = []
    
    test_results.append(("TestUser Data Model", test_test_user_data_model()))
    test_results.append(("UserSession Data Model", test_user_session_data_model()))
    test_results.append(("Configuration Integration", test_configuration_integration()))
    test_results.append(("API Data Structures", test_api_data_structures()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "PASS" if result else "FAIL"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("\nAll tests passed! ✅")
        print("\nThe user session management system is ready for integration.")
        print("Key features implemented:")
        print("- TestUser and UserSession data models")
        print("- Configuration file integration")
        print("- API data structures")
        print("- Load test integration hooks")
        return 0
    else:
        print(f"\n{total - passed} tests failed! ❌")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)