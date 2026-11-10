from datetime import datetime, timezone
from ..extensions import db

class Inventory(db.Model):
    __tablename__ = 'inventory'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    product_size_id = db.Column(db.Integer, db.ForeignKey('product_sizes.id'), nullable=False, unique=True)
    quantity = db.Column(db.Integer, default=0, nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    product = db.relationship('Product', back_populates='inventory')
    size = db.relationship('ProductSize', back_populates='inventory')

    __table_args__ = (
        db.UniqueConstraint('product_id', 'product_size_id', name='uq_inventory_product_size'),
    )

    def __repr__(self):
        return f'<Inventory {self.product_id}:{self.product_size_id} qty={self.quantity}>'