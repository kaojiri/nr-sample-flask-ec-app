#!/usr/bin/env python3
"""
Test script for user session management functionality
"""
import asyncio
import sys
import logging
from pathlib import Path

# Add the load-tester directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from user_session_manager import UserSessionManager, TestUser
from config import config_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_user_session_management():
    """Test user session management functionality"""
    
    print("=" * 60)
    print("Testing User Session Management Functionality")
    print("=" * 60)
    
    try:
        # Initialize user session manager
        print("\n1. Initializing User Session Manager...")
        manager = UserSessionManager()
        
        # Test 1: Check initial state
        print("\n2. Checking initial state...")
        users = manager.get_test_users()
        print(f"   - Found {len(users)} test users")
        for user in users:
            print(f"     * {user.username} ({user.user_id}) - {'Enabled' if user.enabled else 'Disabled'}")
        
        # Test 2: Add a test user
        print("\n3. Adding a test user...")
        test_user = TestUser(
            user_id="test_session_user",
            username="sessiontest@example.com",
            password="testpass123",
            enabled=True,
            description="Test user for session testing"
        )
        
        success = manager.add_test_user(test_user)
        print(f"   - Add user result: {'Success' if success else 'Failed'}")
        
        # Test 3: Get session statistics
        print("\n4. Getting session statistics...")
        stats = manager.get_session_stats()
        print(f"   - Total users: {stats.total_users}")
        print(f"   - Active sessions: {stats.active_sessions}")
        print(f"   - Expired sessions: {stats.expired_sessions}")
        print(f"   - Failed logins: {stats.failed_logins}")
        print(f"   - Successful logins: {stats.successful_logins}")
        
        # Test 4: Attempt to login all users
        print("\n5. Attempting to login all users...")
        sessions = await manager.login_all_users()
        print(f"   - Login attempts completed")
        print(f"   - Successful sessions: {len(sessions)}")
        
        for user_id, session in sessions.items():
            print(f"     * {session.username}: {session.session_cookie[:20]}...")
        
        # Test 5: Get random session
        print("\n6. Testing random session selection...")
        for i in range(3):
            session = manager.get_random_session()
            if session:
                print(f"   - Random session {i+1}: {session.username}")
            else:
                print(f"   - Random session {i+1}: No session available")
        
        # Test 6: Refresh expired sessions
        print("\n7. Testing session refresh...")
        refreshed_count = await manager.refresh_expired_sessions()
        print(f"   - Refreshed sessions: {refreshed_count}")
        
        # Test 7: Get updated statistics
        print("\n8. Getting updated session statistics...")
        stats = manager.get_session_stats()
        print(f"   - Total users: {stats.total_users}")
        print(f"   - Active sessions: {stats.active_sessions}")
        print(f"   - Expired sessions: {stats.expired_sessions}")
        print(f"   - Failed logins: {stats.failed_logins}")
        print(f"   - Successful logins: {stats.successful_logins}")
        
        # Test 8: Logout all users
        print("\n9. Logging out all users...")
        logout_count = await manager.logout_all_users()
        print(f"   - Logged out users: {logout_count}")
        
        # Test 9: Remove test user
        print("\n10. Removing test user...")
        success = manager.remove_test_user("test_session_user")
        print(f"   - Remove user result: {'Success' if success else 'Failed'}")
        
        # Test 10: Final statistics
        print("\n11. Final session statistics...")
        stats = manager.get_session_stats()
        print(f"   - Total users: {stats.total_users}")
        print(f"   - Active sessions: {stats.active_sessions}")
        print(f"   - Expired sessions: {stats.expired_sessions}")
        
        # Cleanup
        await manager.close()
        
        print("\n" + "=" * 60)
        print("User Session Management Test Completed Successfully!")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        print(f"\nTest failed: {e}")
        return False

async def test_configuration_management():
    """Test configuration management for test users"""
    
    print("\n" + "=" * 60)
    print("Testing Configuration Management")
    print("=" * 60)
    
    try:
        # Test 1: Get current configuration
        print("\n1. Getting current configuration...")
        config = config_manager.get_config()
        test_users = config.get("test_users", [])
        print(f"   - Found {len(test_users)} test users in configuration")
        
        # Test 2: Add a test user to configuration
        print("\n2. Adding test user to configuration...")
        new_user = {
            "user_id": "config_test_user",
            "username": "configtest@example.com",
            "password": "configpass123",
            "enabled": True,
            "description": "Test user for configuration testing"
        }
        
        test_users.append(new_user)
        config["test_users"] = test_users
        
        success = config_manager.update_config(config)
        print(f"   - Update configuration result: {'Success' if success else 'Failed'}")
        
        # Test 3: Verify configuration was saved
        print("\n3. Verifying configuration was saved...")
        updated_config = config_manager.get_config()
        updated_test_users = updated_config.get("test_users", [])
        print(f"   - Configuration now has {len(updated_test_users)} test users")
        
        # Find our test user
        found_user = None
        for user in updated_test_users:
            if user.get("user_id") == "config_test_user":
                found_user = user
                break
        
        if found_user:
            print(f"   - Test user found: {found_user['username']}")
        else:
            print("   - Test user not found in configuration")
        
        # Test 4: Remove test user from configuration
        print("\n4. Removing test user from configuration...")
        test_users = [user for user in updated_test_users if user.get("user_id") != "config_test_user"]
        config["test_users"] = test_users
        
        success = config_manager.update_config(config)
        print(f"   - Remove from configuration result: {'Success' if success else 'Failed'}")
        
        # Test 5: Verify removal
        print("\n5. Verifying test user was removed...")
        final_config = config_manager.get_config()
        final_test_users = final_config.get("test_users", [])
        print(f"   - Configuration now has {len(final_test_users)} test users")
        
        print("\n" + "=" * 60)
        print("Configuration Management Test Completed Successfully!")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error(f"Configuration test failed with error: {e}")
        print(f"\nConfiguration test failed: {e}")
        return False

async def main():
    """Main test function"""
    print("Starting User Session Management Tests...")
    
    # Test 1: User session management
    session_test_result = await test_user_session_management()
    
    # Test 2: Configuration management
    config_test_result = await test_configuration_management()
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"User Session Management: {'PASS' if session_test_result else 'FAIL'}")
    print(f"Configuration Management: {'PASS' if config_test_result else 'FAIL'}")
    
    if session_test_result and config_test_result:
        print("\nAll tests passed! ✅")
        return 0
    else:
        print("\nSome tests failed! ❌")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)