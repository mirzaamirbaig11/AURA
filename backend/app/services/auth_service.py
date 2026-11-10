"""
Authentication service.
"""
from datetime import datetime
from ..extensions import db, mail
from ..models import Customer, Admin, AuditLog
from flask import current_app


class AuthService:
    """Handle authentication-related business logic."""

    @staticmethod
    def register_customer(name, email, phone, password):
        """Register a new customer."""
        # Check if email exists
        if Customer.query.filter_by(email=email).first():
            raise ValueError('Email already registered')

        customer = Customer(
            name=name,
            email=email,
            phone=phone,
            is_active=True
        )
        customer.set_password(password)
        db.session.add(customer)
        db.session.commit()

        # Send welcome email
        from ..tasks import dispatch, send_welcome_email
        dispatch(send_welcome_email, customer.id)

        return customer

    @staticmethod
    def authenticate_customer(email, password):
        """Authenticate a customer."""
        customer = Customer.query.filter_by(email=email, is_active=True).first()
        if customer and customer.check_password(password):
            return customer
        return None

    @staticmethod
    def authenticate_admin(email, password):
        """Authenticate an admin."""
        admin = Admin.query.filter_by(email=email, is_active=True).first()
        if admin and admin.check_password(password):
            return admin
        return None

    @staticmethod
    def request_password_reset(email):
        """Generate and send password reset token."""
        customer = Customer.query.filter_by(email=email, is_active=True).first()
        if not customer:
            # Don't reveal if email exists
            return True

        token = customer.generate_reset_token()
        db.session.commit()

        # Send reset email
        from ..tasks import dispatch, send_password_reset_email
        dispatch(send_password_reset_email, customer.id, token)

        return True

    @staticmethod
    def reset_password(token, new_password):
        """Reset password using token."""
        customer = Customer.query.filter_by(reset_token=token).first()
        if not customer or not customer.verify_reset_token(token):
            raise ValueError('Invalid or expired reset token')

        customer.set_password(new_password)
        customer.clear_reset_token()
        db.session.commit()
        return True

    @staticmethod
    def change_password(customer, current_password, new_password):
        """Change password for authenticated user."""
        if not customer.check_password(current_password):
            raise ValueError('Current password is incorrect')
        customer.set_password(new_password)
        db.session.commit()
        return True

    @staticmethod
    def log_admin_action(admin, action, resource_type, resource_id=None, details=None, ip_address=None):
        """Log admin action for audit trail."""
        log = AuditLog(
            admin_id=admin.id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            details=details,
            ip_address=ip_address
        )
        db.session.add(log)
        db.session.commit()
        return log