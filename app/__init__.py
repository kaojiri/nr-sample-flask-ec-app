from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
import os

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()

def create_app():
    app = Flask(__name__)

    # Configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///instance/test.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Setup logging
    from app.logging_config import setup_logging
    setup_logging(app)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    login_manager.login_view = 'auth.login'

    # New Relic Custom Attributes for User Tracking
    @app.before_request
    def add_newrelic_user_attributes():
        """Add user information as custom attributes to New Relic for error tracking"""
        try:
            import newrelic.agent

            if current_user.is_authenticated:
                # New Relic standard attribute for user tracking in Errors Inbox
                newrelic.agent.add_custom_attribute('enduser.id', str(current_user.id))

                # Additional attributes for compatibility and enhanced tracking
                newrelic.agent.add_custom_attribute('userId', str(current_user.id))
                newrelic.agent.add_custom_attribute('user', current_user.username)

                # DEBUG: Log when attributes are set
                app.logger.info(f'✅ New Relic attributes set for user: {current_user.username} (ID: {current_user.id})')
        except ImportError:
            # New Relic is not installed or not running
            app.logger.warning('⚠️ New Relic not available (ImportError)')
            pass
        except Exception as e:
            # Avoid breaking the request if attribute setting fails
            app.logger.error(f'❌ Failed to set New Relic custom attributes: {e}')

    # Register blueprints
    from app.routes import main, auth, products, cart, performance_issues, bulk_users, error_reports
    app.register_blueprint(main.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(products.bp)
    app.register_blueprint(cart.bp)
    app.register_blueprint(performance_issues.bp)
    app.register_blueprint(bulk_users.bp)
    app.register_blueprint(bulk_users.admin_bp)  # 管理画面
    app.register_blueprint(error_reports.error_reports_bp)

    return app
