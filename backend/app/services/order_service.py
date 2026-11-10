"""
Order service for handling order-related business logic.
"""
from datetime import datetime, timezone
from ..extensions import db
from ..models import (
    Order, OrderItem, Product, ProductSize, Inventory,
    Cart, CartItem, CustomerAddress, Coupon
)
from .auth_service import AuthService


class OrderService:
    """Handle order creation, processing, and management."""

    @staticmethod
    def create_order(
        customer,
        items,
        name,
        phone,
        email,
        address,
        city,
        state,
        pincode,
        notes,
        subtotal,
        shipping,
        total,
        payment_method='Cash on Delivery',
        coupon_code=None
    ):
        """Create a new order from cart items."""
        # Validate items and stock
        validated_items = []
        calculated_subtotal = 0
        for item_data in items:
            product = db.session.get(Product, item_data['product'].id)
            size = db.session.get(ProductSize, item_data['size'].id)
            if not product or not product.is_active:
                raise ValueError(f'Product {item_data["product"].name} is no longer available')
            inv = Inventory.query.filter_by(product_size_id=size.id).first()
            if not inv or inv.quantity < item_data['quantity']:
                raise ValueError(f'Insufficient stock for {product.name} ({size.size_label})')
            validated_items.append({
                'product': product,
                'size': size,
                'quantity': item_data['quantity'],
                'price': item_data['price']
            })
            calculated_subtotal += item_data['price'] * item_data['quantity']

        # Verify subtotal matches
        if abs(calculated_subtotal - subtotal) > 0.01:
            raise ValueError('Price mismatch')

        # Validate coupon if provided
        coupon = None
        discount_amount = 0
        if coupon_code:
            coupon = Coupon.query.filter_by(code=coupon_code.upper()).first()
            if coupon:
                is_valid, msg = coupon.is_valid(subtotal)
                if not is_valid:
                    raise ValueError(msg)
                discount_amount = coupon.calculate_discount(subtotal)
                total = subtotal + shipping - discount_amount

        # Generate order number
        order_number = f'AURA-{datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")}-{customer.id}'

        # Create order
        order = Order(
            order_number=order_number,
            customer_id=customer.id,
            customer_name=name,
            customer_phone=phone,
            customer_email=email,
            delivery_address=address,
            delivery_city=city,
            delivery_state=state,
            delivery_pincode=pincode,
            order_notes=notes,
            subtotal=subtotal,
            discount_amount=discount_amount,
            shipping_charge=shipping,
            total_amount=total,
            status='Pending',
            payment_status='Pending',
            payment_method=payment_method,
            coupon_id=coupon.id if coupon else None
        )
        db.session.add(order)
        db.session.flush()

        # Create order items and reduce inventory
        for item_data in validated_items:
            oi = OrderItem(
                order_id=order.id,
                product_id=item_data['product'].id,
                product_size_id=item_data['size'].id,
                product_name=item_data['product'].name,
                size_label=item_data['size'].size_label,
                price=item_data['price'],
                quantity=item_data['quantity']
            )
            db.session.add(oi)

            # Reduce inventory
            inv = Inventory.query.filter_by(product_size_id=item_data['size'].id).first()
            if inv:
                inv.quantity -= item_data['quantity']

        # Update coupon usage
        if coupon:
            coupon.used_count += 1

        db.session.commit()
        return order

    @staticmethod
    def update_order_status(order, new_status, admin=None):
        """Update order status with validation."""
        valid_statuses = ['Pending', 'Confirmed', 'Processing', 'Shipped', 'Delivered', 'Cancelled']
        if new_status not in valid_statuses:
            raise ValueError('Invalid status')

        old_status = order.status
        order.status = new_status

        # If cancelled, restore inventory
        if new_status == 'Cancelled' and old_status != 'Cancelled':
            for item in order.items:
                inv = Inventory.query.filter_by(product_size_id=item.product_size_id).first()
                if inv:
                    inv.quantity += item.quantity

        # If delivered, mark payment as paid if COD
        if new_status == 'Delivered' and order.payment_method == 'Cash on Delivery':
            order.payment_status = 'Paid'

        db.session.commit()

        # Log admin action
        if admin:
            AuthService.log_admin_action(
                admin, 'update_status', 'order', order.id,
                f'Status: {old_status} -> {new_status}',
                ip_address=None
            )

        return order

    @staticmethod
    def process_payment(order, payment_intent_id=None):
        """Mark order as paid."""
        if order.payment_status == 'Paid':
            return order

        order.payment_status = 'Paid'
        order.status = 'Confirmed'
        order.paid_at = datetime.now(timezone.utc)
        if payment_intent_id:
            order.payment_intent_id = payment_intent_id

        db.session.commit()
        return order

    @staticmethod
    def get_order_summary(order):
        """Get formatted order summary for display/email."""
        return {
            'order_number': order.order_number,
            'created_at': order.created_at,
            'status': order.status,
            'payment_status': order.payment_status,
            'payment_method': order.payment_method,
            'subtotal': float(order.subtotal),
            'discount': float(order.discount_amount or 0),
            'shipping': float(order.shipping_charge),
            'total': float(order.total_amount),
            'items': [
                {
                    'name': item.product_name,
                    'size': item.size_label,
                    'price': float(item.price),
                    'quantity': item.quantity,
                    'line_total': float(item.price) * item.quantity
                }
                for item in order.items
            ],
            'shipping_address': {
                'name': order.customer_name,
                'phone': order.customer_phone,
                'email': order.customer_email,
                'address': order.delivery_address,
                'city': order.delivery_city,
                'state': order.delivery_state,
                'pincode': order.delivery_pincode,
            }
        }

    @staticmethod
    def get_customer_orders(customer, page=1, per_page=10):
        """Get paginated orders for a customer."""
        return Order.query.filter_by(customer_id=customer.id)\
            .order_by(Order.created_at.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)

    @staticmethod
    def validate_coupon(code, order_amount):
        """Validate a coupon code."""
        coupon = Coupon.query.filter_by(code=code.upper()).first()
        if not coupon:
            return False, 'Invalid coupon code', None
        is_valid, msg = coupon.is_valid(order_amount)
        return is_valid, msg, coupon