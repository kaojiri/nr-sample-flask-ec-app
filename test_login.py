#!/usr/bin/env python3
from app import create_app
from app.models import User

app = create_app()
with app.app_context():
    user = User.query.filter_by(email='testuser_1761554998_0000@example.com').first()
    if user:
        print('User found:', user.email)
        print('Password check with TestPass123!:', user.check_password('TestPass123!'))
        print('Password hash:', user.password_hash[:50] + '...')
    else:
        print('User not found')