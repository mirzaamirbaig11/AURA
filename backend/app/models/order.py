from datetime import datetime, timezone
from ..extensions import db

ORDER_STATUSES = ['Pending', 'Confirmed', 'Processing', 'Shipped', 'Delivered', 'Cancelled']
PAYMENT_STATUSES = ['Pending', 'Failed', 'Paid', 'Refunded']

class Order(db.Model):
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False, index=True)

    # Shipping snapshot
    customer_name = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)
    customer_email = db.Column(db.String(120), nullable=False)
    delivery_address = db.Column(db.String(255), nullable=False)
    delivery_city = db.Column(db.String(100), nullable=False)
    delivery_state = db.Column(db.String(100), nullable=False)
    delivery_pincode = db.Column(db.String(20), nullable=False)
    order_notes = db.Column(db.Text)

    # Financials
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    discount_amount = db.Column(db.Numeric(10, 2), default=0)
    shipping_charge = db.Column(db.Numeric(10, 2), default=0)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)

    status = db.Column(db.String(20), default='Pending', index=True)
    payment_status = db.Column(db.String(20), default='Pending', index=True)
    payment_method = db.Column(db.String(50), default='Cash on Delivery')

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    customer = db.relationship('Customer', back_populates='orders')
    items = db.relationship('OrderItem', back_populates='order', cascade='all, delete-orphan')

    # Coupon
    coupon_id = db.Column(db.Integer, db.ForeignKey('coupons.id'), nullable=True)
    coupon = db.relationship('Coupon', back_populates='orders')

    # Stripe
    payment_intent_id = db.Column(db.String(100), nullable=True, index=True)
    paid_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<Order {self.order_number}>'