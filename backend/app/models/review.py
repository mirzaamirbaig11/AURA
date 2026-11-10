from datetime import datetime, timezone
from ..extensions import db


class Review(db.Model):
    __tablename__ = 'reviews'

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    rating = db.Column(db.Integer, nullable=False)  # 1-5
    comment = db.Column(db.Text)
    is_approved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    product = db.relationship('Product', back_populates='reviews')
    customer = db.relationship('Customer', back_populates='reviews')

    __table_args__ = (
        db.UniqueConstraint('customer_id', 'product_id', name='uq_customer_product_review'),
    )

    def __repr__(self):
        return f'<Review {self.customer_id}:{self.product_id} rating={self.rating}>'