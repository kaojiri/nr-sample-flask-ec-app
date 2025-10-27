#!/usr/bin/env python3
"""
Admin user creation script
Creates an admin user for the bulk user management system
"""

import sys
import os

# Add parent directory to path to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.user import User

def create_admin():
    app = create_app()

    with app.app_context():
        # Check if admin user already exists
        admin_user = User.query.filter_by(email='admin@example.com').first()
        
        if admin_user:
            print("Admin user already exists:")
            print(f"Email: {admin_user.email}")
            print(f"Username: {admin_user.username}")
            print(f"Is Admin: {admin_user.is_admin}")
            return

        # Create admin user
        print("Creating admin user...")
        admin_user = User(
            username='admin',
            email='admin@example.com',
            is_admin=True
        )
        admin_user.set_password('admin123')
        
        db.session.add(admin_user)
        db.session.commit()
        
        print("Admin user created successfully!")
        print("\nAdmin user credentials:")
        print("Email: admin@example.com")
        print("Username: admin")
        print("Password: admin123")
        print("Is Admin: True")

if __name__ == '__main__':
    create_admin()