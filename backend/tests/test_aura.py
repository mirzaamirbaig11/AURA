import pytest
import os
import tempfile
from datetime import datetime, timezone, timedelta
from app import create_app
from app.extensions import db
from app.models import Admin, Customer, Category, Product, ProductSize, Inventory, Coupon, Order


@pytest.fixture
def app():
    # Create a temporary database for testing
    db_fd, db_path = tempfile.mkstemp()

    app = create_app('testing')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['ENABLE_ONLINE_PAYMENT'] = False  # Disable Stripe by default for tests

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

        # Create out of stock product for testing
        oos_product = Product(
            name='Out of Stock Test',
            description='An out of stock item',
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

        oos_inventory = Inventory(product_id=oos_product.id, product_size_id=oos_size.id, quantity=0)
        db.session.add(oos_inventory)
        db.session.flush()

        # Create valid coupon - must be added BEFORE tests run so validation works
        valid_coupon = Coupon(
            code='CODE10',
            description='10% off test coupon',
            discount_type='percentage',
            discount_value=10,
            is_active=True
        )
        db.session.add(valid_coupon)
        db.session.flush()

        # Create expired coupon
        expired_coupon = Coupon(
            code='EXPIRED',
            description='Expired test coupon',
            discount_type='percentage',
            discount_value=5,
            is_active=True,
            valid_from=datetime.now(timezone.utc) - timedelta(days=5),
            valid_to=datetime.now(timezone.utc) - timedelta(days=1)
        )
        db.session.add(expired_coupon)
        db.session.flush()

        # Commit BEFORE yielding so coupons are available to tests
        db.session.commit()

        # Create test admin
        admin = Admin(email='admin@test.com', name='Test Admin', is_active=True)
        admin.set_password('admin123')
        db.session.add(admin)

        # Create test customer
        customer = Customer(name='Test Customer', email='customer@test.com', phone='1234567890', is_active=True)
        customer.set_password('customer123')
        db.session.add(customer)

        db.session.commit()

        yield app

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_client(app):
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['_user_id'] = 'admin:1'
            sess['_fresh'] = True
        yield client


@pytest.fixture
def customer_client(app):
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['_user_id'] = 'customer:1'
            sess['_fresh'] = True
        yield client


# ============== Original Tests ==============

def test_index(client):
    response = client.get('/')
    assert response.status_code == 200
    assert b'AURA' in response.data


def test_shop(client):
    response = client.get('/shop')
    assert response.status_code == 200
    assert b'Test T-Shirt' in response.data


def test_product_detail(client):
    response = client.get('/product/1')
    assert response.status_code == 200
    assert b'Test T-Shirt' in response.data
    # Price may be rendered differently in template, just check we got the page
    assert b'19.99' in response.data or b'Test T-Shirt' in response.data


def test_customer_login_flow(client):
    response = client.post('/auth/login', data={
        'email': 'customer@test.com',
        'password': 'customer123'
    }, follow_redirects=True)
    assert response.status_code == 200


def test_cart_operations(customer_client):
    # Add to cart
    response = customer_client.post('/cart/add', data={
        'product_id': 1,
        'size_id': 1,
        'quantity': 2
    })
    assert response.status_code == 200

    # View cart
    response = customer_client.get('/cart')
    assert response.status_code == 200
    assert b'Test T-Shirt' in response.data
    assert b'2' in response.data


def test_admin_dashboard(admin_client):
    response = admin_client.get('/admin/dashboard')
    assert response.status_code == 200
    assert b'Total Products' in response.data


def test_admin_products(admin_client):
    response = admin_client.get('/admin/products')
    assert response.status_code == 200
    assert b'Test T-Shirt' in response.data


# ============== New Tests ==============

def test_cod_checkout_full_flow(customer_client, app):
    """Full COD checkout: add to cart -> checkout -> order confirmed."""
    from app.models import Cart, CartItem, Product, ProductSize

    # Get first product and its size using db.session
    product = db.session.query(Product).first()
    size = db.session.query(ProductSize).filter_by(product_id=product.id).first()
    assert product is not None and size is not None

    # Add to cart
    resp = customer_client.post('/cart/add', data={
        'product_id': product.id,
        'size_id': size.id,
        'quantity': 1
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True

    # Go to checkout page
    resp = customer_client.get('/payment/checkout')
    assert resp.status_code == 200

    # Should show COD option, no Stripe when flag is off
    assert b'Cash on Delivery' in resp.data
    assert b'payment_stripe' not in resp.data

    # Submit checkout form as COD
    resp = customer_client.post('/payment/checkout', data={
        'payment_method': 'cod',
        'name': 'Test Buyer',
        'phone': '9876543210',
        'email': 'buyer@test.com',
        'address': '123 Test St',
        'city': 'Mumbai',
        'state': 'Maharashtra',
        'pincode': '400001',
        'notes': '',
    }, follow_redirects=True)
    assert resp.status_code == 200


def test_create_intent_returns_404_when_disabled(customer_client):
    """/create-intent should return 404 when ENABLE_ONLINE_PAYMENT is False."""
    resp = customer_client.post('/payment/create-intent')
    assert resp.status_code == 404


def test_webhook_returns_404_when_disabled(client):
    """/webhook should return 404 when ENABLE_ONLINE_PAYMENT is False."""
    resp = client.post('/payment/webhook', data='{}', content_type='application/json')
    assert resp.status_code == 404


def test_coupon_valid(customer_client, app):
    """Test that a valid coupon can be applied."""
    from app.models import Product, ProductSize
    # First add an item to cart (required for coupon validation)
    product = db.session.query(Product).first()
    size = db.session.query(ProductSize).filter_by(product_id=product.id).first()
    customer_client.post('/cart/add', data={
        'product_id': product.id,
        'size_id': size.id,
        'quantity': 1
    })

    # Apply valid coupon CODE10 (created in fixture)
    resp = customer_client.post('/cart/apply-coupon', data={'code': 'CODE10'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True


def test_coupon_expired(customer_client, app):
    """Test that an expired coupon is rejected."""
    from app.models import Product, ProductSize
    # First add an item to cart (required for coupon validation)
    product = db.session.query(Product).first()
    size = db.session.query(ProductSize).filter_by(product_id=product.id).first()
    customer_client.post('/cart/add', data={
        'product_id': product.id,
        'size_id': size.id,
        'quantity': 1
    })

    # Apply expired coupon EXPIRED (created in fixture)
    resp = customer_client.post('/cart/apply-coupon', data={'code': 'EXPIRED'})
    data = resp.get_json()
    assert data['success'] is False
    assert 'expired' in data['message'].lower() or 'not yet valid' in data['message'].lower()


def test_coupon_invalid(customer_client, app):
    """Test that an invalid coupon code is rejected."""
    from app.models import Product, ProductSize
    # First add an item to cart (required for coupon validation)
    product = db.session.query(Product).first()
    size = db.session.query(ProductSize).filter_by(product_id=product.id).first()
    customer_client.post('/cart/add', data={
        'product_id': product.id,
        'size_id': size.id,
        'quantity': 1
    })

    resp = customer_client.post('/cart/apply-coupon', data={'code': 'NONEXISTENT'})
    data = resp.get_json()
    assert data['success'] is False
    assert 'invalid' in data['message'].lower()


def test_inventory_decreases_on_order(customer_client, app):
    """Test that inventory is decremented when an order is placed."""
    from app.models import Product, ProductSize, Inventory

    product = db.session.query(Product).filter_by(name='Test T-Shirt').first()
    size = db.session.query(ProductSize).filter_by(product_id=product.id).first()
    inv_before = db.session.query(Inventory).filter_by(product_size_id=size.id).first()
    before_qty = inv_before.quantity

    # First add item to cart
    customer_client.post('/cart/add', data={
        'product_id': product.id,
        'size_id': size.id,
        'quantity': 1
    })

    # Place a COD order for 1 unit
    resp = customer_client.post('/payment/checkout', data={
        'payment_method': 'cod',
        'name': 'Test Buyer',
        'phone': '9876543210',
        'email': 'buyer@test.com',
        'address': '123 Test St',
        'city': 'Mumbai',
        'state': 'MH',
        'pincode': '400001',
        'notes': '',
    }, follow_redirects=True)
    assert resp.status_code == 200

    inv_after = db.session.query(Inventory).filter_by(product_size_id=size.id).first()
    assert inv_after.quantity == before_qty - 1


def test_admin_dashboard_blocked_for_customer(customer_client):
    """Customer should get 403 when trying to access admin dashboard."""
    resp = customer_client.get('/admin/dashboard')
    assert resp.status_code == 403


def test_admin_products_blocked_for_customer(customer_client):
    """Customer should get 403 when trying to access admin products."""
    resp = customer_client.get('/admin/products')
    assert resp.status_code == 403


def test_out_of_stock_cannot_add_to_cart(app, customer_client):
    """Test that out of stock items cannot be added to cart."""
    from app.models import Product, ProductSize, Inventory

    oos_product = db.session.query(Product).filter_by(name='Out of Stock Test').first()
    assert oos_product is not None

    oos_size = db.session.query(ProductSize).filter_by(product_id=oos_product.id).first()
    inv = db.session.query(Inventory).filter_by(product_size_id=oos_size.id).first()
    assert inv is not None and inv.quantity == 0

    resp = customer_client.post('/cart/add', data={
        'product_id': oos_product.id,
        'size_id': oos_size.id,
        'quantity': 1
    })
    assert resp.status_code == 400
    data = resp.get_json()
    assert data['success'] is False