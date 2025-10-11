"""
Logging configuration for New Relic Logs in Context
"""
import logging
import sys
from flask import has_request_context, request

class RequestFormatter(logging.Formatter):
    """Custom formatter that adds request context to logs"""

    def format(self, record):
        if has_request_context():
            record.url = request.url
            record.method = request.method
            record.remote_addr = request.remote_addr
            record.user_agent = request.headers.get('User-Agent', 'Unknown')
        else:
            record.url = 'N/A'
            record.method = 'N/A'
            record.remote_addr = 'N/A'
            record.user_agent = 'N/A'

        return super().format(record)


def setup_logging(app):
    """
    Setup logging configuration for the Flask app
    New Relic will automatically capture these logs when properly configured
    """
    # Create custom formatter with request context
    formatter = RequestFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - '
        '[%(method)s %(url)s] - '
        '[IP: %(remote_addr)s] - '
        '%(message)s'
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # Configure app logger
    app.logger.setLevel(logging.INFO)
    app.logger.addHandler(console_handler)

    # Prevent duplicate logs
    app.logger.propagate = False

    # Log startup
    app.logger.info('Application logging configured', extra={
        'event_type': 'app_startup',
        'environment': app.config.get('FLASK_ENV', 'unknown')
    })

    return app.logger
