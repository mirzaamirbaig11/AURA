from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, abort
from flask_login import login_required, current_user
from datetime import datetime, timezone

from ..extensions import db, mail, stripe_imported
from ..models import Order, OrderItem, Product, ProductSize, Inventory, Cart, CartItem, CustomerAddress
from ..services.order_service import OrderService

# Stripe is imported lazily to avoid ImportError when disabled
def _get_stripe():
    """Get stripe module, importing it lazily if needed."""
    if not stripe_imported:
        raise ImportError("Stripe is not installed or not enabled")
    import stripe as stripe_module
    return stripe_module

payment_bp = Blueprint('payment', __name__)


def check_payment_enabled():
    """Check if online payments are enabled."""
    if not current_app.config.get('ENABLE_ONLINE_PAYMENT', False):
        abort(404)


@payment_bp.route('/create-intent', methods=['POST'])
@login_required
def create_payment_intent():
    """Create a Stripe PaymentIntent for the current cart."""
    check_payment_enabled()

    cart = Cart.query.filter_by(customer_id=current_user.id).first()
    if not cart or not cart.items:
        return jsonify({'success': False, 'message': 'Cart is empty'}), 400

    # Validate stock and calculate total
    items = []
    subtotal = 0
    for item in cart.items:
        product = db.session.get(Product, item.product_id)
        size = db.session.get(ProductSize, item.product_size_id)
        if not product or not product.is_active:
            return jsonify({'success': False, 'message': f'Product no longer available'}), 400
        inv = Inventory.query.filter_by(product_size_id=size.id).first()
        if not inv or inv.quantity < item.quantity:
            return jsonify({'success': False, 'message': f'Insufficient stock for {product.name}'}), 400
        items.append({
            'product': product,
            'size': size,
            'quantity': item.quantity,
            'price': float(product.discounted_price)
        })
        subtotal += float(product.discounted_price) * item.quantity

    shipping = 0 if subtotal >= 1000 else 50
    total = subtotal + shipping

    # Convert to smallest currency unit (paise for INR)
    currency = current_app.config.get('STRIPE_CURRENCY', 'inr').lower()
    amount = int(total * 100)  # Stripe expects amount in smallest currency unit

    stripe = _get_stripe()
    try:
        intent = stripe.PaymentIntent.create(
            amount=amount,
            currency=currency,
            metadata={
                'customer_id': current_user.id,
                'customer_email': current_user.email,
            },
            automatic_payment_methods={
                'enabled': True,
            },
        )
        return jsonify({
            'success': True,
            'client_secret': intent.client_secret,
            'amount': amount,
            'currency': currency,
        })
    except stripe.error.StripeError as e:
        current_app.logger.error(f'Stripe error: {e}')
        return jsonify({'success': False, 'message': str(e)}), 500


@payment_bp.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    """Checkout page. Cash on Delivery always works; Stripe only when ENABLE_ONLINE_PAYMENT=true."""

    cart = Cart.query.filter_by(customer_id=current_user.id).first()
    if not cart or not cart.items:
        flash('Your cart is empty.', 'warning')
        return redirect(url_for('frontend.cart'))

    # Validate stock and prepare items
    items = []
    subtotal = 0
    for item in cart.items:
        product = db.session.get(Product, item.product_id)
        size = db.session.get(ProductSize, item.product_size_id)
        if not product or not product.is_active:
            flash(f'{product.name} is no longer available.', 'danger')
            return redirect(url_for('frontend.cart'))
        inv = Inventory.query.filter_by(product_size_id=size.id).first()
        if not inv or inv.quantity < item.quantity:
            flash(f'Insufficient stock for {product.name} ({size.size_label}).', 'danger')
            return redirect(url_for('frontend.cart'))
        items.append({
            'item': item,
            'product': product,
            'size': size,
            'quantity': item.quantity,
            'price': float(product.discounted_price),
            'line_total': float(product.discounted_price) * item.quantity
        })
        subtotal += float(product.discounted_price) * item.quantity

    shipping = 0 if subtotal >= 1000 else 50
    total = subtotal + shipping

    addresses = CustomerAddress.query.filter_by(customer_id=current_user.id).all()

    if request.method == 'POST':
        online_enabled = current_app.config.get('ENABLE_ONLINE_PAYMENT', False)
        payment_method = request.form.get('payment_method') or ('stripe' if online_enabled else 'cod')
        if payment_method != 'stripe' or not online_enabled:
            payment_method = 'cod'
        address_id = request.form.get('address_id', type=int)
        notes = request.form.get('notes', '').strip()

        # Get selected address or use form data
        if address_id:
            addr = CustomerAddress.query.filter_by(id=address_id, customer_id=current_user.id).first()
            if not addr:
                flash('Invalid address.', 'danger')
                return redirect(url_for('payment.checkout'))
            name = addr.name
            phone = addr.phone
            email = current_user.email
            delivery_address = addr.address_line
            city = addr.city
            state = addr.state
            pincode = addr.pincode
        else:
            name = request.form.get('name', '').strip()
            phone = request.form.get('phone', '').strip()
            email = request.form.get('email', '').strip()
            delivery_address = request.form.get('address', '').strip()
            city = request.form.get('city', '').strip()
            state = request.form.get('state', '').strip()
            pincode = request.form.get('pincode', '').strip()

            errors = []
            if not name: errors.append('Name is required.')
            if not phone: errors.append('Phone is required.')
            if not email: errors.append('Email is required.')
            if not delivery_address: errors.append('Address is required.')
            if not city: errors.append('City is required.')
            if not state: errors.append('State is required.')
            if not pincode: errors.append('PIN code is required.')
            if errors:
                for e in errors:
                    flash(e, 'danger')
                return redirect(url_for('payment.checkout'))

        # Create order with pending payment
        order_service = OrderService()
        try:
            order = order_service.create_order(
                customer=current_user,
                items=items,
                name=name,
                phone=phone,
                email=email,
                address=delivery_address,
                city=city,
                state=state,
                pincode=pincode,
                notes=notes,
                subtotal=subtotal,
                shipping=shipping,
                total=total,
                payment_method='Cash on Delivery' if payment_method == 'cod' else 'Online (Stripe)',
                coupon_code=(request.form.get('coupon_code') or '').strip() or None
            )
        except ValueError as e:
            flash(str(e), 'danger')
            return redirect(url_for('payment.checkout'))

        if payment_method == 'stripe':
            # Create payment intent for this order
            stripe = _get_stripe()
            currency = current_app.config.get('STRIPE_CURRENCY', 'inr').lower()
            amount = int(round(float(order.total_amount) * 100))
            try:
                intent = stripe.PaymentIntent.create(
                    amount=amount,
                    currency=currency,
                    metadata={
                        'order_id': order.id,
                        'order_number': order.order_number,
                    },
                    automatic_payment_methods={'enabled': True},
                )
                order.payment_intent_id = intent.id
                db.session.commit()
                return render_template('payment/stripe_checkout.html',
                                       order=order,
                                       client_secret=intent.client_secret,
                                       stripe_publishable_key=current_app.config.get('STRIPE_PUBLISHABLE_KEY'))
            except stripe.error.StripeError as e:
                current_app.logger.error(f'Stripe error: {e}')
                flash('Payment initialization failed. Please try again.', 'danger')
                return redirect(url_for('payment.checkout'))
        else:
            # Cash on Delivery
            order.payment_status = 'Pending'
            order.status = 'Confirmed'
            db.session.commit()
            # Clear cart
            CartItem.query.filter_by(cart_id=cart.id).delete()
            db.session.commit()
            flash('Order placed successfully!', 'success')
            return redirect(url_for('frontend.order_confirmation', order_id=order.id))

    return render_template('payment/checkout.html',
                           items=items,
                           subtotal=subtotal,
                           shipping=shipping,
                           total=total,
                           addresses=addresses,
                           enable_online_payment=current_app.config.get('ENABLE_ONLINE_PAYMENT', False))


@payment_bp.route('/success/<int:order_id>')
@login_required
def payment_success(order_id):
    """Payment success page."""
    check_payment_enabled()

    order = Order.query.filter_by(id=order_id, customer_id=current_user.id).first_or_404()
    if order.payment_status != 'Paid':
        flash('Payment not yet confirmed.', 'warning')
    return render_template('payment/success.html', order=order)


@payment_bp.route('/cancel/<int:order_id>')
@login_required
def payment_cancel(order_id):
    """Payment cancelled page."""
    check_payment_enabled()

    order = Order.query.filter_by(id=order_id, customer_id=current_user.id).first_or_404()
    return render_template('payment/cancel.html', order=order)


@payment_bp.route('/webhook', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook events."""
    check_payment_enabled()

    stripe = _get_stripe()

    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = current_app.config.get('STRIPE_WEBHOOK_SECRET')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError:
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError:
        return 'Invalid signature', 400

    # Handle the event
    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        _handle_payment_success(payment_intent)
    elif event['type'] == 'payment_intent.payment_failed':
        payment_intent = event['data']['object']
        _handle_payment_failed(payment_intent)

    return '', 200


def _handle_payment_success(payment_intent):
    """Process successful payment."""
    if not current_app.config.get('ENABLE_ONLINE_PAYMENT', False):
        return

    order_id = payment_intent.metadata.get('order_id')
    if not order_id:
        return

    order = db.session.get(Order, int(order_id))
    if not order:
        return

    if order.payment_status == 'Paid':
        return  # Already processed

    order.payment_status = 'Paid'
    order.status = 'Confirmed'
    order.paid_at = datetime.now(timezone.utc)
    db.session.commit()

    # Clear cart
    cart = Cart.query.filter_by(customer_id=order.customer_id).first()
    if cart:
        CartItem.query.filter_by(cart_id=cart.id).delete()
        db.session.commit()

    # Send confirmation email (async via Celery)
    from ..tasks import dispatch, send_order_confirmation_email
    dispatch(send_order_confirmation_email, order.id)


def _handle_payment_failed(payment_intent):
    """Process failed payment."""
    if not current_app.config.get('ENABLE_ONLINE_PAYMENT', False):
        return

    order_id = payment_intent.metadata.get('order_id')
    if not order_id:
        return

    order = db.session.get(Order, int(order_id))
    if not order:
        return

    order.payment_status = 'Failed'
    order.status = 'Cancelled'
    db.session.commit()

    # Restore inventory
    for item in order.items:
        inv = Inventory.query.filter_by(product_size_id=item.product_size_id).first()
        if inv:
            inv.quantity += item.quantity
    db.session.commit()