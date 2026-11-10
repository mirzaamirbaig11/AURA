from datetime import datetime, timezone
from ..extensions import db

class CartItem(db.Model):
    __tablename__ = 'cart_items'

    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey('carts.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    product_size_id = db.Column(db.Integer, db.ForeignKey('product_sizes.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    cart = db.relationship('Cart', back_populates='items')
    product = db.relationship('Product')
    size = db.relationship('ProductSize')

    __table_args__ = (
        db.UniqueConstraint('cart_id', 'product_id', 'product_size_id', name='uq_cart_item'),
    )

    def __repr__(self):
        return f'<CartItem {self.product_id} x{self.quantity}>'