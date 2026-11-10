from datetime import datetime, timezone
from ..extensions import db

class WishlistItem(db.Model):
    __tablename__ = 'wishlist_items'

    id = db.Column(db.Integer, primary_key=True)
    wishlist_id = db.Column(db.Integer, db.ForeignKey('wishlists.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    wishlist = db.relationship('Wishlist', back_populates='items')
    product = db.relationship('Product')

    __table_args__ = (
        db.UniqueConstraint('wishlist_id', 'product_id', name='uq_wishlist_item'),
    )

    def __repr__(self):
        return f'<WishlistItem {self.product_id}>'