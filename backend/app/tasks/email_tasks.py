"""
Email tasks for background processing.
"""
try:
    from celery import shared_task
except ImportError:  # Celery not installed: tasks run as normal functions
    def shared_task(*_args, **_kwargs):
        def decorator(func):
            return func
        return decorator
from flask import current_app
from flask_mail import Message


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3}, retry_backoff=True)
def send_welcome_email(customer_id):
    """Send welcome email to new customer."""
    from .. import create_app
    from ..extensions import db, mail
    from ..models import Customer

    app = create_app()
    with app.app_context():
        customer = db.session.get(Customer, customer_id)
        if not customer:
            return

        msg = Message(
            subject='Welcome to AURA!',
            recipients=[customer.email],
            sender=current_app.config.get('MAIL_DEFAULT_SENDER')
        )
        msg.html = f'''
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #0d0d0d; color: #ffffff; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background-color: #1a1a1a; padding: 30px; border-radius: 8px; border: 1px solid #333;">
                <div style="text-align: center; margin-bottom: 30px;">
                    <h1 style="color: #e60000; font-weight: 900; letter-spacing: 2px;">AURA</h1>
                    <p style="color: #cccccc;">Premium Luxury Streetwear</p>
                </div>
                <h2 style="color: #ffffff;">Welcome, {customer.name}!</h2>
                <p>Thank you for joining AURA. We're excited to have you as part of our community.</p>
                <p>Explore our collections of premium streetwear - from hoodies and t-shirts to jeans and jackets.</p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{current_app.config.get('FRONTEND_URL', 'http://localhost:5000')}/shop"
                       style="background: linear-gradient(135deg, #e60000 0%, #990000 100%);
                            color: white; padding: 15px 30px; text-decoration: none;
                            border-radius: 4px; font-weight: bold; display: inline-block;">
                        Start Shopping
                    </a>
                </div>
                <p style="color: #888; font-size: 14px;">Follow us on social media for updates and exclusive offers.</p>
            </div>
        </body>
        </html>
        '''
        try:
            mail.send(msg)
        except Exception as e:
            current_app.logger.error(f'Failed to send welcome email: {e}')
            raise


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3}, retry_backoff=True)
def send_password_reset_email(customer_id, token):
    """Send password reset email."""
    from .. import create_app
    from ..extensions import db, mail
    from ..models import Customer

    app = create_app()
    with app.app_context():
        customer = db.session.get(Customer, customer_id)
        if not customer:
            return

        reset_url = f"{current_app.config.get('FRONTEND_URL', 'http://localhost:5000')}/auth/reset-password?token={token}"

        msg = Message(
            subject='Reset Your AURA Password',
            recipients=[customer.email],
            sender=current_app.config.get('MAIL_DEFAULT_SENDER')
        )
        msg.html = f'''
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #0d0d0d; color: #ffffff; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background-color: #1a1a1a; padding: 30px; border-radius: 8px; border: 1px solid #333;">
                <div style="text-align: center; margin-bottom: 30px;">
                    <h1 style="color: #e60000; font-weight: 900; letter-spacing: 2px;">AURA</h1>
                </div>
                <h2 style="color: #ffffff;">Password Reset Request</h2>
                <p>Hi {customer.name},</p>
                <p>You requested to reset your password. Click the button below to create a new password:</p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_url}"
                       style="background: linear-gradient(135deg, #e60000 0%, #990000 100%);
                            color: white; padding: 15px 30px; text-decoration: none;
                            border-radius: 4px; font-weight: bold; display: inline-block;">
                        Reset Password
                    </a>
                </div>
                <p style="color: #888; font-size: 14px;">
                    This link expires in 1 hour. If you didn't request this, please ignore this email.
                </p>
            </div>
        </body>
        </html>
        '''
        try:
            mail.send(msg)
        except Exception as e:
            current_app.logger.error(f'Failed to send password reset email: {e}')
            raise


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3}, retry_backoff=True)
def send_order_confirmation_email(order_id):
    """Send order confirmation email."""
    from .. import create_app
    from ..extensions import db, mail
    from ..models import Order
    from ..services.order_service import OrderService

    app = create_app()
    with app.app_context():
        order = db.session.get(Order, order_id)
        if not order:
            return

        summary = OrderService.get_order_summary(order)

        msg = Message(
            subject=f'Order Confirmation - {order.order_number}',
            recipients=[order.customer_email],
            sender=current_app.config.get('MAIL_DEFAULT_SENDER')
        )
        items_html = ''
        for item in summary['items']:
            items_html += f'''
            <tr style="border-bottom: 1px solid #333;">
                <td style="padding: 12px; color: #ffffff;">{item['name']}</td>
                <td style="padding: 12px; color: #ffffff;">{item['size']}</td>
                <td style="padding: 12px; color: #ffffff;">₹{item['price']:.2f}</td>
                <td style="padding: 12px; color: #ffffff;">{item['quantity']}</td>
                <td style="padding: 12px; color: #ffffff;">₹{item['line_total']:.2f}</td>
            </tr>
            '''

        msg.html = f'''
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #0d0d0d; color: #ffffff; padding: 20px;">
            <div style="max-width: 700px; margin: 0 auto; background-color: #1a1a1a; padding: 30px; border-radius: 8px; border: 1px solid #333;">
                <div style="text-align: center; margin-bottom: 30px;">
                    <h1 style="color: #e60000; font-weight: 900; letter-spacing: 2px;">AURA</h1>
                    <p style="color: #cccccc;">Premium Luxury Streetwear</p>
                </div>
                <h2 style="color: #ffffff;">Order Confirmed!</h2>
                <p>Thank you for your order, {summary['shipping_address']['name']}.</p>
                <p><strong>Order Number:</strong> {summary['order_number']}</p>
                <p><strong>Order Date:</strong> {summary['created_at'].strftime('%B %d, %Y')}</p>
                <p><strong>Payment Method:</strong> {summary['payment_method']}</p>
                <p><strong>Payment Status:</strong> <span style="color: {'#4ade80' if summary['payment_status'] == 'Paid' else '#fbbf24'};">{summary['payment_status']}</span></p>

                <h3 style="margin-top: 30px; color: #ffffff;">Order Items</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr style="background-color: #333; color: #ffffff;">
                            <th style="padding: 12px; text-align: left;">Product</th>
                            <th style="padding: 12px; text-align: left;">Size</th>
                            <th style="padding: 12px; text-align: right;">Price</th>
                            <th style="padding: 12px; text-align: center;">Qty</th>
                            <th style="padding: 12px; text-align: right;">Total</th>
                        </tr>
                    </thead>
                    <tbody>
                        {items_html}
                    </tbody>
                </table>

                <div style="margin-top: 20px; text-align: right;">
                    <p><strong>Subtotal:</strong> ₹{summary['subtotal']:.2f}</p>
                    {'<p><strong>Discount:</strong> -₹' + f"{summary['discount']:.2f}</p>" if summary['discount'] > 0 else ''}
                    <p><strong>Shipping:</strong> ₹{summary['shipping']:.2f}</p>
                    <p style="font-size: 1.2rem; color: #e60000;"><strong>Total: ₹{summary['total']:.2f}</strong></p>
                </div>

                <h3 style="margin-top: 30px; color: #ffffff;">Shipping Address</h3>
                <p style="white-space: pre-line; color: #cccccc;">
{summary['shipping_address']['name']}
{summary['shipping_address']['address']}
{summary['shipping_address']['city']}, {summary['shipping_address']['state']} {summary['shipping_address']['pincode']}
Phone: {summary['shipping_address']['phone']}
                </p>

                <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #333; text-align: center; color: #888; font-size: 14px;">
                    <p>Questions? Contact us at <a href="https://wa.me/91{current_app.config.get('WHATSAPP_NUMBER', '8527756728')}" style="color: #e60000;">WhatsApp</a></p>
                </div>
            </div>
        </body>
        </html>
        '''
        try:
            mail.send(msg)
        except Exception as e:
            current_app.logger.error(f'Failed to send order confirmation email: {e}')
            raise


@shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 3}, retry_backoff=True)
def send_admin_order_notification(order_id):
    """Send new order notification to admin."""
    from .. import create_app
    from ..extensions import db, mail
    from ..models import Order, Admin
    from ..services.order_service import OrderService

    app = create_app()
    with app.app_context():
        order = db.session.get(Order, order_id)
        if not order:
            return

        admins = Admin.query.filter_by(is_active=True).all()
        if not admins:
            return

        summary = OrderService.get_order_summary(order)

        for admin in admins:
            msg = Message(
                subject=f'New Order: {order.order_number}',
                recipients=[admin.email],
                sender=current_app.config.get('MAIL_DEFAULT_SENDER')
            )
            msg.html = f'''
            <html>
            <body style="font-family: Arial, sans-serif; background-color: #0d0d0d; color: #ffffff; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; background-color: #1a1a1a; padding: 30px; border-radius: 8px; border: 1px solid #333;">
                    <h2 style="color: #e60000;">New Order Received</h2>
                    <p><strong>Order:</strong> {summary['order_number']}</p>
                    <p><strong>Customer:</strong> {summary['shipping_address']['name']} ({summary['shipping_address']['email']})</p>
                    <p><strong>Total:</strong> ₹{summary['total']:.2f}</p>
                    <p><strong>Payment:</strong> {summary['payment_method']} ({summary['payment_status']})</p>
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{current_app.config.get('FRONTEND_URL', 'http://localhost:5000')}/admin/orders/{order.id}"
                           style="background: linear-gradient(135deg, #e60000 0%, #990000 100%);
                                color: white; padding: 15px 30px; text-decoration: none;
                                border-radius: 4px; font-weight: bold; display: inline-block;">
                            View Order
                        </a>
                    </div>
                </div>
            </body>
            </html>
            '''
            try:
                mail.send(msg)
            except Exception as e:
                current_app.logger.error(f'Failed to send admin notification: {e}')
                raise