from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required
from app import db
from app.models import User

bp = Blueprint('auth', __name__, url_prefix='/auth')

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        if User.query.filter_by(email=email).first():
            flash('Email already registered')
            return redirect(url_for('auth.register'))

        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('Registration successful!')
        return redirect(url_for('auth.login'))

    return render_template('register.html')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # DEBUG: Log request details
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Login attempt - Content-Type: {request.content_type}")
        logger.info(f"Login attempt - Form data: {dict(request.form)}")
        logger.info(f"Login attempt - Request data: {request.data[:100] if request.data else 'None'}")

        email = request.form.get('email')
        password = request.form.get('password')

        logger.info(f"Login attempt - Email: {email}, Password: {'***' if password else 'None'}")

        user = User.query.filter_by(email=email).first()

        if user:
            # Debug: Test password directly
            from werkzeug.security import check_password_hash
            direct_check = check_password_hash(user.password_hash, password)
            method_check = user.check_password(password)

            logger.info(f"User found: {user.email}")
            logger.info(f"Password (len={len(password) if password else 0}): {password[:5]}... (first 5 chars)")
            logger.info(f"Password hash: {user.password_hash[:50]}...")
            logger.info(f"Direct check_password_hash result: {direct_check}")
            logger.info(f"User.check_password result: {method_check}")

            password_check = method_check

            if password_check:
                logger.info(f"Login successful for user: {email}")
                login_user(user)
                next_page = request.args.get('next')
                return redirect(next_page or url_for('main.index'))
            else:
                logger.warning(f"Password check failed for user: {email}")
        else:
            logger.warning(f"User not found: {email}")

        logger.warning(f"Login failed for user: {email} - User found: {user is not None}")
        flash('Invalid email or password')

    return render_template('login.html')

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))
