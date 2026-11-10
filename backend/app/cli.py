"""
CLI commands for the application.
"""
import click
from flask.cli import with_appcontext


def init_app(app):
    """Register CLI commands."""
    app.cli.add_command(create_admin)
    app.cli.add_command(init_categories)
    app.cli.add_command(create_coupon)


@click.command('create-admin')
@click.option('--email', default='admin@aura.com', help='Admin email')
@click.option('--password', default='admin123', help='Admin password')
@click.option('--name', default='AURA Admin', help='Admin name')
@with_appcontext
def create_admin(email, password, name):
    """Create an admin user."""
    from .extensions import db
    from .models import Admin

    existing = Admin.query.filter_by(email=email).first()
    if existing:
        click.echo(f'Admin with email {email} already exists.')
        return

    admin = Admin(email=email, name=name, is_active=True)
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    click.echo(f'Admin created: {email}')


@click.command('init-categories')
@with_appcontext
def init_categories():
    """Initialize default categories."""
    from .extensions import db
    from .models import Category

    categories = [
        ('Jersey', 'Comfortable and stylish jerseys'),
        ('Jeans', 'Premium denim jeans'),
        ('T-Shirts', 'Casual and graphic tees'),
        ('Shirts', 'Formal and casual shirts'),
        ('Hoodies', 'Warm and stylish hoodies'),
        ('Cargoes', 'Functional cargo pants'),
        ('Trousers', 'Smart and casual trousers'),
        ('Jackets', 'Trendy jackets and outerwear'),
    ]

    for name, desc in categories:
        if not Category.query.filter_by(name=name).first():
            cat = Category(name=name, description=desc, is_active=True)
            db.session.add(cat)

    db.session.commit()
    click.echo('Default categories initialized.')


@click.command('create-coupon')
@click.argument('code')
@click.option('--type', 'discount_type', type=click.Choice(['percentage', 'fixed']), default='percentage')
@click.option('--value', type=float, required=True, help='Discount value (percentage or fixed amount)')
@click.option('--min-amount', type=float, default=0, help='Minimum order amount')
@click.option('--limit', type=int, help='Usage limit')
@click.option('--description', default='', help='Coupon description')
@with_appcontext
def create_coupon(code, discount_type, value, min_amount, limit, description):
    """Create a new coupon."""
    from .extensions import db
    from .models import Coupon

    if Coupon.query.filter_by(code=code.upper()).first():
        click.echo(f'Coupon {code} already exists.')
        return

    coupon = Coupon(
        code=code.upper(),
        description=description,
        discount_type=discount_type,
        discount_value=value,
        minimum_order_amount=min_amount,
        usage_limit=limit,
        is_active=True
    )
    db.session.add(coupon)
    db.session.commit()
    click.echo(f'Coupon created: {code.upper()} ({discount_type} {value})')