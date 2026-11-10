from datetime import datetime, timezone
from ..extensions import db

class Wishlist(db.Model):
    __tablename__ = 'wishlists'

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), unique=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    customer = db.relationship('Customer', back_populates='wishlist')
    items = db.relationship('WishlistItem', back_populates='wishlist', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Wishlist {self.id}>'