#!/usr/bin/env python
"""Script to create an admin user."""

import os
import sys

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Admin
from dotenv import load_dotenv

load_dotenv()

app = create_app()

def create_admin():
    with app.app_context():
        email = os.environ.get('ADMIN_EMAIL', 'admin@aura.com')
        password = os.environ.get('ADMIN_PASSWORD', 'admin123')
        name = os.environ.get('ADMIN_NAME', 'AURA Admin')

        existing_admin = Admin.query.filter_by(email=email).first()
        if existing_admin:
            print(f"Admin user with email '{email}' already exists.")
            return

        admin = Admin(email=email, name=name, is_active=True)
        admin.set_password(password)

        db.session.add(admin)
        db.session.commit()

        print(f"Admin user created successfully!")
        print(f"  Email: {email}")
        print(f"  Password: {password}")
        print(f"  Login URL: /admin/login")

if __name__ == '__main__':
    create_admin()