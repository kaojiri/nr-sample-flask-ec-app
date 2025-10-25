#!/usr/bin/env python3
"""
Manual test script for user login functionality
This script can be used to test user login when Web UI has issues
"""
import asyncio
import sys
from user_session_manager import get_user_session_manager

async def test_user_login():
    """Test user login functionality"""
    print("🧪 Testing User Login Functionality\n")
    
    try:
        # Get user session manager
        manager = get_user_session_manager()
        print(f"✅ UserSessionManager loaded successfully")
        print(f"   - Total users configured: {len(manager.test_users)}")
        
        # Display configured users
        print("\n📋 Configured Users:")
        for user_id, user in manager.test_users.items():
            status = "✅ Enabled" if user.enabled else "❌ Disabled"
            print(f"   - {user_id}: {user.username} ({status})")
        
        # Test login for all users
        print("\n🔐 Testing Login for All Users...")
        sessions = await manager.login_all_users()
        
        print(f"\n📊 Login Results:")
        print(f"   - Successful logins: {len(sessions)}")
        print(f"   - Failed logins: {manager.stats.failed_logins}")
        
        # Display session details
        if sessions:
            print("\n🎯 Active Sessions:")
            for user_id, session in sessions.items():
                print(f"   - User {user_id} ({session.username})")
                print(f"     Session Cookie: {session.session_cookie[:50]}...")
                print(f"     Login Time: {session.login_time}")
        else:
            print("\n❌ No active sessions found")
            
        # Test session retrieval
        print("\n🎲 Testing Random Session Selection...")
        random_session = manager.get_random_session()
        if random_session:
            print(f"   ✅ Random session selected: {random_session.username}")
        else:
            print("   ❌ No random session available")
            
        return len(sessions) > 0
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test function"""
    print("=" * 60)
    print("🚀 Load Tester - User Login Manual Test")
    print("=" * 60)
    
    success = await test_user_login()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ User login functionality is working correctly!")
        print("💡 You can now use the load tester with user sessions.")
    else:
        print("❌ User login functionality has issues.")
        print("💡 Please check the configuration and try again.")
    print("=" * 60)
    
    return 0 if success else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)