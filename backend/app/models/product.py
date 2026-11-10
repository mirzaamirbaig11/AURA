from datetime import datetime, timezone
from ..extensions import db

class Product(db.Model):
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False, index=True)
    description = db.Column(db.Text)
    original_price = db.Column(db.Numeric(10, 2), nullable=False)
    discounted_price = db.Column(db.Numeric(10, 2), nullable=False)
    is_active = db.Column(db.Boolean, default=True, index=True)
    is_featured = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    category = db.relationship('Category', back_populates='products')
    images = db.relationship('ProductImage', back_populates='product', cascade='all, delete-orphan')
    sizes = db.relationship('ProductSize', back_populates='product', cascade='all, delete-orphan')
    inventory = db.relationship('Inventory', back_populates='product', cascade='all, delete-orphan')
    order_items = db.relationship('OrderItem', back_populates='product')
    reviews = db.relationship('Review', back_populates='product')

    def effective_price(self):
        return float(self.discounted_price) if self.discounted_price else float(self.original_price)

    def get_average_rating(self):
        """Calculate average rating from approved reviews."""
        approved_reviews = [r for r in self.reviews if r.is_approved]
        if not approved_reviews:
            return 0
        return sum(r.rating for r in approved_reviews) / len(approved_reviews)

    def get_review_count(self):
        """Get count of approved reviews."""
        return len([r for r in self.reviews if r.is_approved])

    def __repr__(self):
        return f'<Product {self.name}>'