from datetime import datetime, timezone
from ..extensions import db

class ProductSize(db.Model):
    __tablename__ = 'product_sizes'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    size_label = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    product = db.relationship('Product', back_populates='sizes')
    inventory = db.relationship('Inventory', back_populates='size', uselist=False, cascade='all, delete-orphan')

    __table_args__ = (
        db.UniqueConstraint('product_id', 'size_label', name='uq_product_size'),
    )

    def __repr__(self):
        return f'<ProductSize {self.product_id}:{self.size_label}>'