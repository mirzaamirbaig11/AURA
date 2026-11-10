from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, timezone
from ..extensions import db
import secrets


class Customer(UserMixin, db.Model):
    __tablename__ = 'customers'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20))
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    # Password reset
    reset_token = db.Column(db.String(100), nullable=True, index=True)
    reset_token_expires = db.Column(db.DateTime, nullable=True)

    addresses = db.relationship('CustomerAddress', back_populates='customer', cascade='all, delete-orphan')
    orders = db.relationship('Order', back_populates='customer', cascade='all, delete-orphan')
    cart = db.relationship('Cart', back_populates='customer', uselist=False, cascade='all, delete-orphan')
    wishlist = db.relationship('Wishlist', back_populates='customer', uselist=False, cascade='all, delete-orphan')
    reviews = db.relationship('Review', back_populates='customer', cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        return f"customer:{self.id}"

    def generate_reset_token(self, expires_in=3600):
        """Generate a password reset token."""
        self.reset_token = secrets.token_urlsafe(32)
        self.reset_token_expires = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        return self.reset_token

    def verify_reset_token(self, token):
        """Verify a password reset token."""
        if not self.reset_token or not self.reset_token_expires:
            return False
        expires = self.reset_token_expires
        if expires.tzinfo is None:  # SQLite stores naive datetimes (UTC)
            expires = expires.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires:
            return False
        return secrets.compare_digest(self.reset_token, token)

    def clear_reset_token(self):
        """Clear the reset token after use."""
        self.reset_token = None
        self.reset_token_expires = None

    def __repr__(self):
        return f'<Customer {self.email}>'