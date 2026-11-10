from datetime import datetime, timezone
from ..extensions import db


def _as_utc(dt):
    """SQLite returns naive datetimes; treat them as UTC so comparisons don't crash."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class Coupon(db.Model):
    __tablename__ = 'coupons'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    description = db.Column(db.String(200))
    discount_type = db.Column(db.String(20), default='percentage')  # 'percentage' or 'fixed'
    discount_value = db.Column(db.Numeric(10, 2), nullable=False)
    minimum_order_amount = db.Column(db.Numeric(10, 2), default=0)
    usage_limit = db.Column(db.Integer)
    used_count = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True, index=True)
    valid_from = db.Column(db.DateTime)
    valid_to = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationship
    orders = db.relationship('Order', back_populates='coupon')

    def is_valid(self, order_amount=0):
        """Check if coupon is valid for use."""
        if not self.is_active:
            return False, 'Coupon is not active'

        now = datetime.now(timezone.utc)
        if self.valid_from and now < _as_utc(self.valid_from):
            return False, 'Coupon is not yet valid'
        if self.valid_to and now > _as_utc(self.valid_to):
            return False, 'Coupon has expired'

        if self.usage_limit and self.used_count >= self.usage_limit:
            return False, 'Coupon usage limit reached'

        if order_amount < float(self.minimum_order_amount):
            return False, f'Minimum order amount is ₹{self.minimum_order_amount:.2f}'

        return True, 'Valid'

    def calculate_discount(self, order_amount):
        """Calculate discount amount for given order total."""
        if self.discount_type == 'percentage':
            discount = float(order_amount) * (float(self.discount_value) / 100)
        else:  # fixed
            discount = float(self.discount_value)
        return min(discount, float(order_amount))

    def __repr__(self):
        return f'<Coupon {self.code}>'