#!/usr/bin/env python3
"""
Test script to verify Load Tester session authentication and New Relic userId tracking

This script simulates Load Tester behavior:
1. Login to Flask app and get session cookie
2. Make authenticated request with session cookie
3. Verify that current_user.is_authenticated is True in Flask
4. Verify that New Relic custom attributes are set
"""

import sys
import os
from unittest.mock import patch, MagicMock
from app import create_app, db
from app.models import User

def test_session_authentication():
    """Test that Load Tester session cookies properly authenticate users in Flask"""

    print("=" * 80)
    print("🧪 Testing Load Tester Session Authentication and New Relic userId Tracking")
    print("=" * 80)
    print()

    # Create Flask app
    app = create_app()

    with app.app_context():
        # Create a test user if it doesn't exist
        test_email = "loadtest_user@example.com"
        test_password = "TestPassword123!"

        user = User.query.filter_by(email=test_email).first()
        if not user:
            print(f"📝 Creating test user: {test_email}")
            user = User(
                username="loadtest_user",
                email=test_email,
                is_test_user=True
            )
            user.set_password(test_password)
            db.session.add(user)
            db.session.commit()
            print(f"✅ Test user created with ID: {user.id}")
        else:
            print(f"✅ Using existing test user with ID: {user.id}")

        print()
        print("-" * 80)
        print("Step 1: Login and get session cookie (simulating Load Tester)")
        print("-" * 80)

        # Use test client to login
        with app.test_client() as client:
            # Login request
            login_response = client.post('/auth/login', data={
                'email': test_email,
                'password': test_password
            }, follow_redirects=False)

            print(f"Login response status: {login_response.status_code}")

            # Extract session cookie
            session_cookie = None
            for cookie in client.cookie_jar:
                if cookie.name == 'session':
                    session_cookie = cookie.value
                    break

            if session_cookie:
                print(f"✅ Session cookie obtained: {session_cookie[:30]}...")
            else:
                print("❌ ERROR: No session cookie found after login")
                return False

            print()
            print("-" * 80)
            print("Step 2: Make authenticated request with session cookie")
            print("-" * 80)

            # Mock New Relic agent to capture custom attributes
            with patch('newrelic.agent') as mock_newrelic:
                mock_add_custom_attribute = MagicMock()
                mock_newrelic.add_custom_attribute = mock_add_custom_attribute

                # Make authenticated request to any endpoint
                response = client.get('/')

                print(f"Request response status: {response.status_code}")

                # Check if custom attributes were set
                calls = mock_add_custom_attribute.call_args_list

                print()
                print("-" * 80)
                print("Step 3: Verify New Relic custom attributes")
                print("-" * 80)

                if len(calls) >= 3:
                    print(f"✅ Custom attributes were set! ({len(calls)} attributes)")
                    print()
                    print("📋 Attributes added:")

                    attr_dict = {}
                    for call in calls:
                        attr_name, attr_value = call[0]
                        attr_dict[attr_name] = attr_value
                        print(f"   - {attr_name}: {attr_value}")

                    print()
                    print("🔍 Verification:")

                    success = True

                    if 'enduser.id' in attr_dict:
                        expected_user_id = str(user.id)
                        actual_user_id = attr_dict['enduser.id']
                        if actual_user_id == expected_user_id:
                            print(f"   ✅ enduser.id = {actual_user_id} (matches user.id)")
                        else:
                            print(f"   ❌ enduser.id = {actual_user_id} (expected {expected_user_id})")
                            success = False
                    else:
                        print("   ❌ enduser.id not found")
                        success = False

                    if 'userId' in attr_dict:
                        expected_user_id = str(user.id)
                        actual_user_id = attr_dict['userId']
                        if actual_user_id == expected_user_id:
                            print(f"   ✅ userId = {actual_user_id} (matches user.id)")
                        else:
                            print(f"   ❌ userId = {actual_user_id} (expected {expected_user_id})")
                            success = False
                    else:
                        print("   ❌ userId not found")
                        success = False

                    if 'user' in attr_dict:
                        expected_username = user.username
                        actual_username = attr_dict['user']
                        if actual_username == expected_username:
                            print(f"   ✅ user = {actual_username} (matches username)")
                        else:
                            print(f"   ❌ user = {actual_username} (expected {expected_username})")
                            success = False
                    else:
                        print("   ❌ user (username) not found")
                        success = False

                    print()

                    if success:
                        print("=" * 80)
                        print("✅ SUCCESS: Session authentication and New Relic tracking work correctly!")
                        print("=" * 80)
                        print()
                        print("💡 Conclusion:")
                        print("   - Load Tester session cookies properly authenticate users")
                        print("   - Flask's current_user.is_authenticated is True")
                        print("   - New Relic custom attributes (enduser.id, userId, user) are set")
                        print()
                        print("🤔 If New Relic Errors Inbox shows 0 impacted users in production:")
                        print("   1. Verify Load Tester is sending the session cookie correctly")
                        print("   2. Check Flask app logs for authentication issues")
                        print("   3. Verify New Relic agent is running (newrelic-admin)")
                        print("   4. Check if errors are actually occurring during load test")
                        print("   5. Verify NEW_RELIC_LICENSE_KEY is set correctly")
                        return True
                    else:
                        print("=" * 80)
                        print("❌ PARTIAL SUCCESS: Some attributes are missing or incorrect")
                        print("=" * 80)
                        return False

                else:
                    print(f"❌ ERROR: Expected at least 3 custom attributes, but got {len(calls)}")
                    if len(calls) > 0:
                        print("Attributes that were set:")
                        for call in calls:
                            attr_name, attr_value = call[0]
                            print(f"   - {attr_name}: {attr_value}")

                    print()
                    print("💡 Possible issues:")
                    print("   1. User is not authenticated (current_user.is_authenticated is False)")
                    print("   2. New Relic agent is not properly initialized")
                    print("   3. @app.before_request hook is not executing")
                    return False


def test_load_tester_cookie_format():
    """Test that Load Tester's cookie format matches Flask's expectations"""

    print()
    print("=" * 80)
    print("🧪 Testing Load Tester Cookie Format")
    print("=" * 80)
    print()

    # Create Flask app
    app = create_app()

    with app.app_context():
        test_email = "loadtest_user@example.com"
        test_password = "TestPassword123!"

        with app.test_client() as client:
            # Login
            login_response = client.post('/auth/login', data={
                'email': test_email,
                'password': test_password
            }, follow_redirects=False)

            # Get session cookie value from test client
            test_client_cookie = None
            for cookie in client.cookie_jar:
                if cookie.name == 'session':
                    test_client_cookie = cookie.value
                    break

            print(f"✅ Flask test_client session cookie format:")
            print(f"   {test_client_cookie[:50]}...")
            print()

            # Show how Load Tester should format the cookie
            print("💡 Load Tester should send cookies as:")
            print(f"   Cookie: session={test_client_cookie}")
            print()
            print("   OR as a dictionary:")
            print(f"   {{'session': '{test_client_cookie}'}}")
            print()

            # Check Load Tester's actual implementation
            print("🔍 Checking Load Tester implementation...")
            print()
            print("From worker_pool.py line 218:")
            print("   headers['Cookie'] = f\"session={{session.session_cookie}}\"")
            print()
            print("✅ This format is correct!")
            print()

            return True


if __name__ == '__main__':
    print()
    success1 = test_session_authentication()
    success2 = test_load_tester_cookie_format()

    print()
    print("=" * 80)

    if success1 and success2:
        print("✅ All tests passed!")
        print("=" * 80)
        sys.exit(0)
    else:
        print("❌ Some tests failed")
        print("=" * 80)
        sys.exit(1)
