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
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'postgresql://user:password@localhost/ecdb')
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
        except ImportError:
            # New Relic is not installed or not running
            pass
        except Exception as e:
            # Avoid breaking the request if attribute setting fails
            app.logger.debug(f'Failed to set New Relic custom attributes: {e}')

    # Register blueprints
    from app.routes import main, auth, products, cart, performance_issues
    app.register_blueprint(main.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(products.bp)
    app.register_blueprint(cart.bp)
    app.register_blueprint(performance_issues.bp)

    return app
