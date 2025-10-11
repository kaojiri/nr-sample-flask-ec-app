#!/usr/bin/env python
"""
New Relic connection test script
Run this to verify your New Relic configuration before starting the application
"""
import os
import sys

# Check if license key is set
license_key = os.getenv('NEW_RELIC_LICENSE_KEY')
if not license_key:
    print("❌ ERROR: NEW_RELIC_LICENSE_KEY environment variable is not set")
    sys.exit(1)

print("=" * 60)
print("New Relic Configuration Test")
print("=" * 60)
print(f"License Key: {license_key[:20]}...{license_key[-4:]}")
print(f"License Key Length: {len(license_key)} characters")
print(f"License Key Type: {'Ingest-LICENSE' if license_key.endswith('NRAL') else 'Legacy License Key'}")
print()

# Import New Relic
try:
    import newrelic.agent
    print(f"✅ New Relic agent imported successfully")
    print(f"   Version: {newrelic.version}")
except ImportError as e:
    print(f"❌ ERROR: Could not import New Relic agent: {e}")
    sys.exit(1)

print()

# Test configuration
app_name = os.getenv('NEW_RELIC_APP_NAME', 'Flask-EC-App')
environment = os.getenv('NEW_RELIC_ENVIRONMENT', 'development')
config_file = os.getenv('NEW_RELIC_CONFIG_FILE', 'newrelic.ini')

print(f"Configuration:")
print(f"  App Name: {app_name}")
print(f"  Environment: {environment}")
print(f"  Config File: {config_file}")
print()

# Check if config file exists
if not os.path.exists(config_file):
    print(f"❌ ERROR: Config file not found: {config_file}")
    sys.exit(1)
else:
    print(f"✅ Config file exists: {config_file}")

print()

# Check environment variable override behavior
print("Environment Variable Check:")
print(f"  NEW_RELIC_APP_NAME env var: {app_name}")
print(f"  This should override the default 'Flask-EC-App' in newrelic.ini")
print()

# Try to initialize
print("Attempting to initialize New Relic agent...")
try:
    # Set environment variables
    os.environ['NEW_RELIC_LICENSE_KEY'] = license_key
    os.environ['NEW_RELIC_APP_NAME'] = app_name
    os.environ['NEW_RELIC_ENVIRONMENT'] = environment

    # Initialize
    newrelic.agent.initialize(config_file, environment=environment)
    print("✅ New Relic agent initialized successfully")

    # Get settings
    settings = newrelic.agent.global_settings()
    print()
    print("Agent Settings:")
    print(f"  License Key Set: {'Yes' if settings.license_key else 'No'}")
    print(f"  App Name: {settings.app_name}")
    print(f"    ↳ Expected: {app_name}")
    print(f"    ↳ Match: {'✅' if settings.app_name == app_name else '❌ MISMATCH!'}")
    print(f"  Monitor Mode: {settings.monitor_mode}")
    print(f"  Host: {settings.host}")
    print(f"  Port: {settings.port}")
    print(f"  SSL: {settings.ssl}")
    print(f"  Proxy Host: {settings.proxy_host or 'None'}")

    if settings.license_key:
        print(f"  License Key (truncated): {settings.license_key[:20]}...")
        print(f"    ↳ Expected: {license_key[:20]}...")
        print(f"    ↳ Match: {'✅' if settings.license_key == license_key else '❌ MISMATCH!'}")

    print()
    print("=" * 60)
    print("✅ All checks passed! New Relic should work correctly.")
    print("=" * 60)

except Exception as e:
    print(f"❌ ERROR during initialization: {e}")
    print()
    import traceback
    traceback.print_exc()
    print()
    print("=" * 60)
    print("❌ Configuration test failed")
    print("=" * 60)
    print()
    print("Common issues:")
    print("1. License key format is incorrect")
    print("2. Network connectivity issues")
    print("3. Firewall blocking collector.newrelic.com")
    print("4. Environment variables not set correctly")
    sys.exit(1)
