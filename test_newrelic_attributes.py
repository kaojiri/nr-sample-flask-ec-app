#!/usr/bin/env python
"""
Test script to verify New Relic custom attributes are being set correctly
"""

import sys
from unittest.mock import Mock, patch, MagicMock
from app import create_app


def test_newrelic_attributes():
    """Test that New Relic custom attributes are set for authenticated users"""

    print("🧪 Testing New Relic Custom Attributes Implementation\n")

    # Create Flask app
    app = create_app()

    # Mock New Relic agent
    with patch('newrelic.agent') as mock_newrelic:
        mock_add_custom_attribute = MagicMock()
        mock_newrelic.add_custom_attribute = mock_add_custom_attribute

        # Create test client
        with app.test_client() as client:
            with app.test_request_context():
                # Mock authenticated user
                from flask_login import login_user
                from app.models import User

                # Create a mock user
                mock_user = Mock(spec=User)
                mock_user.id = 12345
                mock_user.username = 'testuser'
                mock_user.is_authenticated = True

                with patch('flask_login.utils._get_user', return_value=mock_user):
                    # Trigger before_request hook
                    app.preprocess_request()

                    # Verify custom attributes were set
                    calls = mock_add_custom_attribute.call_args_list

                    if len(calls) >= 3:
                        print("✅ Custom attributes were set successfully!\n")
                        print("📋 Attributes added:")
                        for call in calls:
                            attr_name, attr_value = call[0]
                            print(f"   - {attr_name}: {attr_value}")

                        # Verify specific attributes
                        attr_dict = {call[0][0]: call[0][1] for call in calls}

                        print("\n🔍 Verification:")

                        if 'enduser.id' in attr_dict:
                            print(f"   ✅ enduser.id = {attr_dict['enduser.id']} (New Relic standard)")
                        else:
                            print("   ❌ enduser.id not found")

                        if 'userId' in attr_dict:
                            print(f"   ✅ userId = {attr_dict['userId']} (compatibility)")
                        else:
                            print("   ❌ userId not found")

                        if 'user' in attr_dict:
                            print(f"   ✅ user = {attr_dict['user']} (username)")
                        else:
                            print("   ❌ user not found")

                        print("\n✨ Implementation successful! User information will appear in New Relic Errors Inbox.")
                        return True
                    else:
                        print(f"❌ Expected 3 custom attributes, but got {len(calls)}")
                        return False


if __name__ == '__main__':
    success = test_newrelic_attributes()
    sys.exit(0 if success else 1)
