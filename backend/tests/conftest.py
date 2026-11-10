import pytest
import os
import tempfile
from datetime import datetime, timezone, timedelta
from app import create_app
from app.extensions import db
from app.models import (
    Admin, Customer, Category, Product, ProductSize,
    Inventory, Order, Coupon, Cart, CartItem, CustomerAddress
)

@pytest.fixture
def app():
    # Create a temporary database for testing
    db_fd, db_path = tempfile.mkstemp()

    app = create_app('testing')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['ENABLE_ONLINE_PAYMENT'] = False  # Disable Stripe for tests

    with app.app_context():
        db.create_all()

        # Create test category
        category = Category(name='T-Shirts', description='Test category', is_active=True)
        db.session.add(category)
        db.session.flush()

        # Create test product with inventory
        product = Product(
            name='Test T-Shirt',
            description='A test t-shirt',
            category_id=category.id,
            original_price=29.99,
            discounted_price=19.99,
            is_active=True
        )
        db.session.add(product)
        db.session.flush()

        # Create test size and inventory
        size = ProductSize(product_id=product.id, size_label='M')
        db.session.add(size)
        db.session.flush()

        inventory = Inventory(product_id=product.id, product_size_id=size.id, quantity=10)
        db.session.add(inventory)
        db.session.flush()

        # Create out-of-stock product for testing
        oos_product = Product(
            name='Out of Stock Test',
            description='A product with no stock',
            category_id=category.id,
            original_price=49.99,
            discounted_price=39.99,
            is_active=True
        )
        db.session.add(oos_product)
        db.session.flush()

        oos_size = ProductSize(product_id=oos_product.id, size_label='L')
        db.session.add(oos_size)
        db.session.flush()

        # Explicitly set quantity to 0 for out of stock
        oos_inventory = Inventory(product_id=oos_product.id, product_size_id=oos_size.id, quantity=0)
        db.session.add(oos_inventory)
        db.session.flush()

        # Create valid coupon
        valid_coupon = Coupon(
            code='CODE10',
            description='10% off coupon',
            discount_type='percentage',
            discount_value=10,
            is_active=True,
            valid_from=datetime.now(timezone.utc),
            valid_to=datetime.now(timezone.utc) + timedelta(days=7)
        )
        db.session.add(valid_coupon)
        db.session.flush()

        # Create expired coupon
        expired_coupon = Coupon(
            code='EXPIRED',
            description='Expired coupon',
            discount_type='percentage',
            discount_value=5,
            is_active=True,
            valid_from=datetime.now(timezone.utc) - timedelta(days=5),
            valid_to=datetime.now(timezone.utc) - timedelta(days=1)
        )
        db.session.add(expired_coupon)
        db.session.commit()

        yield app

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


@pytest.fixture
def admin_client(app):
    """Create an admin client (authenticated as admin)."""
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['_user_id'] = 'admin:1'
            sess['_fresh'] = True
        yield client


@pytest.fixture
def customer_client(app):
    """Create a customer client (authenticated as customer)."""
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['_user_id'] = 'customer:1'
            sess['_fresh'] = True
        yield client


@pytest.fixture
def admin_broken_session(client):
    """Client with session pretending to be customer trying to access admin."""
    with client.session_transaction() as sess:
        sess['_user_id'] = 'customer:1'  # Customer ID, not admin
        sess['_fresh'] = True
    yield client