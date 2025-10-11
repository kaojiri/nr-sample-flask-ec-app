#!/bin/bash
set -e

if [ -n "$NEW_RELIC_LICENSE_KEY" ]; then
    echo "=========================================="
    echo "Starting with New Relic monitoring..."
    echo "License Key: ${NEW_RELIC_LICENSE_KEY:0:20}...${NEW_RELIC_LICENSE_KEY: -4}"
    echo "License Key Length: ${#NEW_RELIC_LICENSE_KEY} characters"
    echo "App Name: ${NEW_RELIC_APP_NAME:-Flask-EC-App}"
    echo "Environment: ${NEW_RELIC_ENVIRONMENT:-production}"
    echo "=========================================="

    # Set default values if not provided
    export NEW_RELIC_APP_NAME="${NEW_RELIC_APP_NAME:-Flask-EC-App}"
    export NEW_RELIC_ENVIRONMENT="${NEW_RELIC_ENVIRONMENT:-production}"

    # Critical: Set config file path
    export NEW_RELIC_CONFIG_FILE=/app/newrelic.ini

    # Enable detailed logging for debugging
    export NEW_RELIC_LOG=stdout
    export NEW_RELIC_LOG_LEVEL=debug

    # Disable SSL verification if needed (only for debugging)
    # export NEW_RELIC_SSL=false

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
    echo "Starting application with New Relic..."
    echo "=========================================="

    # Run with New Relic using newrelic-admin
    exec newrelic-admin run-program gunicorn \
        --bind 0.0.0.0:5000 \
        --workers 4 \
        --timeout 120 \
        --log-level info \
        --access-logfile - \
        --error-logfile - \
        run:app

else
    echo "=========================================="
    echo "Starting without New Relic monitoring..."
    echo "NEW_RELIC_LICENSE_KEY is not set"
    echo "=========================================="
    exec gunicorn \
        --bind 0.0.0.0:5000 \
        --workers 4 \
        --timeout 120 \
        --log-level info \
        --access-logfile - \
        --error-logfile - \
        run:app
fi
