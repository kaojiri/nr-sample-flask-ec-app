#!/bin/bash
set -e

if [ -n "$NEW_RELIC_LICENSE_KEY" ]; then
    echo "=========================================="
    echo "Starting Distributed Service with New Relic monitoring..."
    echo "License Key: ${NEW_RELIC_LICENSE_KEY:0:20}...${NEW_RELIC_LICENSE_KEY: -4}"
    echo "License Key Length: ${#NEW_RELIC_LICENSE_KEY} characters"
    echo "App Name: ${NEW_RELIC_APP_NAME:-Flask-EC-Distributed-Service}"
    echo "Environment: ${NEW_RELIC_ENVIRONMENT:-development}"
    echo "=========================================="

    # Set default values if not provided
    export NEW_RELIC_APP_NAME="${NEW_RELIC_APP_NAME:-Flask-EC-Distributed-Service}"
    export NEW_RELIC_ENVIRONMENT="${NEW_RELIC_ENVIRONMENT:-development}"

    # Critical: Set config file path
    export NEW_RELIC_CONFIG_FILE=/app/newrelic.ini

    # Enable detailed logging for debugging
    export NEW_RELIC_LOG=stdout
    export NEW_RELIC_LOG_LEVEL=info

    echo "Configuration:"
    echo "  Config File: $NEW_RELIC_CONFIG_FILE"
    echo "  Log Level: $NEW_RELIC_LOG_LEVEL"
    echo ""

    # Verify New Relic installation
    echo "Verifying New Relic installation..."
    python -c "import newrelic.agent; print('New Relic version:', newrelic.version)" || {
        echo "ERROR: Could not import New Relic agent"
        exit 1
    }

    # Test configuration
    echo "Testing New Relic configuration..."
    python -c "
import os
import newrelic.agent

try:
    # Initialize with environment
    newrelic.agent.initialize('${NEW_RELIC_CONFIG_FILE}', environment='${NEW_RELIC_ENVIRONMENT}')

    # Get settings
    settings = newrelic.agent.global_settings()
    print('Config loaded successfully!')
    print('  License key configured:', 'Yes' if settings.license_key else 'No')
    print('  App name:', settings.app_name)
    print('  Monitor mode:', settings.monitor_mode)
    print('  Host:', settings.host)
except Exception as e:
    print('ERROR during initialization:', str(e))
    import traceback
    traceback.print_exc()
" || {
        echo "WARNING: Configuration test failed, but will try to proceed..."
    }

    echo ""
    echo "Starting distributed service with New Relic..."
    echo "=========================================="

    # Run with New Relic using newrelic-admin
    exec newrelic-admin run-program python app.py

else
    echo "=========================================="
    echo "Starting distributed service without New Relic monitoring..."
    echo "NEW_RELIC_LICENSE_KEY is not set"
    echo "=========================================="
    exec python app.py
fi