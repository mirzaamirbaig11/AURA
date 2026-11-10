from datetime import datetime
from ..extensions import db

class OrderItem(db.Model):
    __tablename__ = 'order_items'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True) # Can remain if product deleted
    product_size_id = db.Column(db.Integer, db.ForeignKey('product_sizes.id'), nullable=True)

    # Historical snapshot
    product_name = db.Column(db.String(200), nullable=False)
    size_label = db.Column(db.String(20), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

    order = db.relationship('Order', back_populates='items')
    product = db.relationship('Product', back_populates='order_items')

    def __repr__(self):
        return f'<OrderItem {self.product_name} x{self.quantity}>'