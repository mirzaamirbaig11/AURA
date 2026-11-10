from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort, current_app
from flask_login import login_required, current_user
from sqlalchemy import desc, func, or_
from datetime import datetime, timedelta, timezone
from werkzeug.utils import secure_filename
import os

from ..extensions import db
from ..models import (
    Admin, Customer, Category, Product, ProductImage, ProductSize,
    Inventory, Order, OrderItem, NewsletterSubscriber, AuditLog,
    Coupon, Review
)
from ..services.auth_service import AuthService
from ..services.order_service import OrderService

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    from flask_login import login_user
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        admin = Admin.query.filter_by(email=email, is_active=True).first()
        if admin and admin.check_password(password):
            login_user(admin, remember=True)
            flash('Welcome back, Admin!', 'success')
            return redirect(url_for('admin.dashboard'))

        flash('Invalid credentials.', 'danger')
    return render_template('admin/login.html')


def admin_required():
    if not current_user.is_authenticated or not isinstance(current_user, Admin):
        abort(403)


def log_action(action, resource_type, resource_id=None, details=None):
    if current_user.is_authenticated and isinstance(current_user, Admin):
        log = AuditLog(
            admin_id=current_user.id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            details=details,
            ip_address=request.remote_addr
        )
        db.session.add(log)


@admin_bp.route('/')
@admin_bp.route('/dashboard')
@login_required
def dashboard():
    admin_required()

    stats = {
        'total_products': Product.query.count(),
        'total_categories': Category.query.count(),
        'total_customers': Customer.query.count(),
        'total_orders': Order.query.count(),
        'pending_orders': Order.query.filter_by(status='Pending').count(),
        'completed_orders': Order.query.filter_by(status='Delivered').count(),
        'total_sales': db.session.query(func.coalesce(func.sum(Order.total_amount), 0)).filter(
            Order.payment_status == 'Paid'
        ).scalar() or 0,
        'low_stock_count': db.session.query(func.count(Inventory.id)).filter(
            Inventory.quantity <= 10,
            Inventory.quantity > 0
        ).scalar() or 0,
        'out_of_stock_count': db.session.query(func.count(Inventory.id)).filter(
            Inventory.quantity == 0
        ).scalar() or 0,
    }

    recent_orders = Order.query.order_by(desc(Order.created_at)).limit(10).all()

    # Sales data for last 7 days
    today = datetime.now(timezone.utc).date()
    sales_data = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_start = datetime.combine(day, datetime.min.time())
        day_end = datetime.combine(day, datetime.max.time())
        sales = db.session.query(func.coalesce(func.sum(Order.total_amount), 0)).filter(
            Order.created_at.between(day_start, day_end)
        ).scalar() or 0
        sales_data.append({'date': day.strftime('%a'), 'amount': float(sales)})

    return render_template('admin/dashboard.html', stats=stats, recent_orders=recent_orders, sales_data=sales_data)


# Products
@admin_bp.route('/products')
@login_required
def products():
    admin_required()
    page = request.args.get('page', 1, type=int)
    search = request.args.get('q', '').strip()
    category_id = request.args.get('category', type=int)
    status = request.args.get('status', '')

    query = Product.query

    if search:
        query = query.filter(or_(
            Product.name.ilike(f'%{search}%'),
            Product.description.ilike(f'%{search}%')
        ))
    if category_id:
        query = query.filter_by(category_id=category_id)
    if status == 'active':
        query = query.filter_by(is_active=True)
    elif status == 'inactive':
        query = query.filter_by(is_active=False)

    pagination = query.order_by(desc(Product.created_at)).paginate(page=page, per_page=20, error_out=False)

    categories = Category.query.all()
    product_images = {}
    for p in pagination.items:
        primary_img = ProductImage.query.filter_by(product_id=p.id, is_primary=True).first()
        if not primary_img:
            primary_img = ProductImage.query.filter_by(product_id=p.id).first()
        product_images[p.id] = primary_img.image_filename if primary_img else None

    return render_template('admin/products.html', pagination=pagination, categories=categories,
                           search=search, category_id=category_id, status=status, product_images=product_images)


@admin_bp.route('/products/add', methods=['GET', 'POST'])
@login_required
def add_product():
    admin_required()
    categories = Category.query.filter_by(is_active=True).all()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        category_id = request.form.get('category_id', type=int)
        original_price = request.form.get('original_price', type=float)
        discounted_price = request.form.get('discounted_price', type=float)
        is_active = bool(request.form.get('is_active'))
        is_featured = bool(request.form.get('is_featured'))

        sizes_text = request.form.get('sizes', '')
        sizes = [s.strip().upper() for s in sizes_text.split('\n') if s.strip()]

        errors = []
        if not name: errors.append('Product name is required.')
        if not category_id: errors.append('Category is required.')
        if original_price is None or original_price <= 0: errors.append('Valid original price is required.')
        if discounted_price is None or discounted_price <= 0: errors.append('Valid discounted price is required.')
        if not sizes: errors.append('At least one size is required.')

        if errors:
            for e in errors: flash(e, 'danger')
        else:
            product = Product(
                name=name,
                description=description,
                category_id=category_id,
                original_price=original_price,
                discounted_price=discounted_price,
                is_active=is_active,
                is_featured=is_featured
            )
            db.session.add(product)
            db.session.flush()

            for size_label in sizes:
                ps = ProductSize(product_id=product.id, size_label=size_label)
                db.session.add(ps)
                db.session.flush()
                db.session.add(Inventory(product_id=product.id, product_size_id=ps.id, quantity=0))

            images = request.files.getlist('images')
            for i, img in enumerate(images):
                if img and img.filename:
                    filename = secure_filename(f"{product.id}_{i}_{img.filename}")
                    save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'products')
                    os.makedirs(save_path, exist_ok=True)
                    img.save(os.path.join(save_path, filename))
                    db.session.add(ProductImage(product_id=product.id, image_filename=filename, is_primary=(i==0)))

            db.session.commit()
            log_action('create', 'product', product.id, f'Created product: {name}')
            flash('Product added successfully.', 'success')
            return redirect(url_for('admin.products'))

    return render_template('admin/product_form.html', categories=categories, product=None)


@admin_bp.route('/products/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_product(id):
    admin_required()
    product = Product.query.get_or_404(id)
    categories = Category.query.filter_by(is_active=True).all()

    if request.method == 'POST':
        product.name = request.form.get('name', '').strip()
        product.description = request.form.get('description', '').strip()
        product.category_id = request.form.get('category_id', type=int)
        product.original_price = request.form.get('original_price', type=float)
        product.discounted_price = request.form.get('discounted_price', type=float)
        product.is_active = bool(request.form.get('is_active'))
        product.is_featured = bool(request.form.get('is_featured'))

        sizes_text = request.form.get('sizes', '')
        sizes = [s.strip().upper() for s in sizes_text.split('\n') if s.strip()]

        errors = []
        if not product.name: errors.append('Product name is required.')
        if not product.category_id: errors.append('Category is required.')
        if product.original_price is None or product.original_price <= 0: errors.append('Valid original price required.')
        if product.discounted_price is None or product.discounted_price <= 0: errors.append('Valid discounted price required.')

        if errors:
            for e in errors: flash(e, 'danger')
        else:
            existing_sizes = {s.size_label: s for s in product.sizes}
            for size_label in sizes:
                if size_label not in existing_sizes:
                    ps = ProductSize(product_id=product.id, size_label=size_label)
                    db.session.add(ps)
                    db.session.flush()
                    db.session.add(Inventory(product_id=product.id, product_size_id=ps.id, quantity=0))
                del existing_sizes[size_label]

            for size_label, size_obj in existing_sizes.items():
                inv = Inventory.query.filter_by(product_size_id=size_obj.id).first()
                if inv and inv.quantity == 0:
                    oi = OrderItem.query.filter_by(product_size_id=size_obj.id).first()
                    if not oi:
                        db.session.delete(size_obj)

            images = request.files.getlist('images')
            for i, img in enumerate(images):
                if img and img.filename:
                    filename = secure_filename(f"{product.id}_{datetime.now(timezone.utc).timestamp()}_{img.filename}")
                    save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'products')
                    os.makedirs(save_path, exist_ok=True)
                    img.save(os.path.join(save_path, filename))
                    db.session.add(ProductImage(product_id=product.id, image_filename=filename, is_primary=(i==0 and not product.images)))

            db.session.commit()
            log_action('update', 'product', product.id, f'Updated product: {product.name}')
            flash('Product updated.', 'success')
            return redirect(url_for('admin.products'))

    sizes_data = []
    for s in product.sizes:
        inv = Inventory.query.filter_by(product_size_id=s.id).first()
        sizes_data.append({
            'id': s.id,
            'label': s.size_label,
            'quantity': inv.quantity if inv else 0
        })

    return render_template('admin/product_form.html', categories=categories, product=product, sizes_data=sizes_data)


@admin_bp.route('/products/delete/<int:id>', methods=['POST'])
@login_required
def delete_product(id):
    admin_required()
    product = Product.query.get_or_404(id)
    name = product.name
    db.session.delete(product)
    db.session.commit()
    log_action('delete', 'product', id, f'Deleted product: {name}')
    flash('Product deleted.', 'success')
    return redirect(url_for('admin.products'))


# Categories
@admin_bp.route('/categories')
@login_required
def categories():
    admin_required()
    cats = Category.query.order_by(Category.name).all()
    return render_template('admin/categories.html', categories=cats)


@admin_bp.route('/categories/add', methods=['GET', 'POST'])
@login_required
def add_category():
    admin_required()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        is_active = bool(request.form.get('is_active'))

        if not name:
            flash('Category name is required.', 'danger')
        elif Category.query.filter_by(name=name).first():
            flash('Category already exists.', 'danger')
        else:
            cat = Category(name=name, description=description, is_active=is_active)

            img = request.files.get('image')
            if img and img.filename:
                filename = secure_filename(f"cat_{name}_{img.filename}")
                save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'categories')
                os.makedirs(save_path, exist_ok=True)
                img.save(os.path.join(save_path, filename))
                cat.image_filename = filename

            db.session.add(cat)
            db.session.commit()
            log_action('create', 'category', cat.id, f'Created category: {name}')
            flash('Category added.', 'success')
            return redirect(url_for('admin.categories'))
    return render_template('admin/category_form.html', category=None)


@admin_bp.route('/categories/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_category(id):
    admin_required()
    cat = Category.query.get_or_404(id)
    if request.method == 'POST':
        cat.name = request.form.get('name', '').strip()
        cat.description = request.form.get('description', '').strip()
        cat.is_active = bool(request.form.get('is_active'))

        img = request.files.get('image')
        if img and img.filename:
            filename = secure_filename(f"cat_{cat.name}_{img.filename}")
            save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'categories')
            os.makedirs(save_path, exist_ok=True)
            img.save(os.path.join(save_path, filename))
            cat.image_filename = filename

        db.session.commit()
        log_action('update', 'category', cat.id, f'Updated category: {cat.name}')
        flash('Category updated.', 'success')
        return redirect(url_for('admin.categories'))
    return render_template('admin/category_form.html', category=cat)


@admin_bp.route('/categories/delete/<int:id>', methods=['POST'])
@login_required
def delete_category(id):
    admin_required()
    cat = Category.query.get_or_404(id)
    if cat.products:
        flash('Cannot delete category with products.', 'danger')
    else:
        name = cat.name
        db.session.delete(cat)
        db.session.commit()
        log_action('delete', 'category', id, f'Deleted category: {name}')
        flash('Category deleted.', 'success')
    return redirect(url_for('admin.categories'))


# Orders
@admin_bp.route('/orders')
@login_required
def orders():
    admin_required()
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')
    search = request.args.get('q', '').strip()

    query = Order.query

    if status:
        query = query.filter_by(status=status)
    if search:
        query = query.filter(or_(
            Order.order_number.ilike(f'%{search}%'),
            Order.customer_name.ilike(f'%{search}%'),
            Order.customer_email.ilike(f'%{search}%')
        ))

    pagination = query.order_by(desc(Order.created_at)).paginate(page=page, per_page=20, error_out=False)

    return render_template('admin/orders.html', pagination=pagination, status=status, search=search,
                           order_statuses=['Pending', 'Confirmed', 'Processing', 'Shipped', 'Delivered', 'Cancelled'])


@admin_bp.route('/orders/<int:id>')
@login_required
def order_detail(id):
    admin_required()
    order = Order.query.get_or_404(id)
    return render_template('admin/order_detail.html', order=order, order_images=_order_images(order))


@admin_bp.route('/orders/<int:id>/status', methods=['POST'])
@login_required
def update_order_status(id):
    admin_required()
    order = Order.query.get_or_404(id)
    new_status = request.form.get('status', '')

    valid_statuses = ['Pending', 'Confirmed', 'Processing', 'Shipped', 'Delivered', 'Cancelled']
    if new_status in valid_statuses:
        OrderService.update_order_status(order, new_status, current_user)
        flash('Order status updated.', 'success')
    else:
        flash('Invalid status.', 'danger')
    return redirect(url_for('admin.order_detail', id=id))


# Customers
@admin_bp.route('/customers')
@login_required
def customers():
    admin_required()
    page = request.args.get('page', 1, type=int)
    search = request.args.get('q', '').strip()
    status = request.args.get('status', '')

    query = Customer.query
    if search:
        query = query.filter(or_(
            Customer.name.ilike(f'%{search}%'),
            Customer.email.ilike(f'%{search}%')
        ))
    if status == 'active':
        query = query.filter_by(is_active=True)
    elif status == 'inactive':
        query = query.filter_by(is_active=False)

    pagination = query.order_by(desc(Customer.created_at)).paginate(page=page, per_page=20, error_out=False)
    return render_template('admin/customers.html', pagination=pagination, search=search, status=status)


@admin_bp.route('/customers/<int:id>')
@login_required
def customer_detail(id):
    admin_required()
    customer = Customer.query.get_or_404(id)
    orders = Order.query.filter_by(customer_id=id).order_by(desc(Order.created_at)).all()
    return render_template('admin/customer_detail.html', customer=customer, orders=orders)


@admin_bp.route('/customers/<int:id>/toggle', methods=['POST'])
@login_required
def toggle_customer(id):
    admin_required()
    customer = Customer.query.get_or_404(id)
    customer.is_active = not customer.is_active
    db.session.commit()
    log_action('toggle_status', 'customer', id, f'is_active={customer.is_active}')
    return jsonify({'success': True, 'is_active': customer.is_active})


# Inventory
@admin_bp.route('/inventory')
@login_required
def inventory():
    admin_required()
    page = request.args.get('page', 1, type=int)
    search = request.args.get('q', '').strip()
    low_stock = request.args.get('low_stock', type=int)

    query = db.session.query(Product, ProductSize, Inventory).join(
        ProductSize, Product.id == ProductSize.product_id
    ).join(
        Inventory, ProductSize.id == Inventory.product_size_id
    ).filter(Product.is_active == True)

    if search:
        query = query.filter(Product.name.ilike(f'%{search}%'))
    if low_stock:
        query = query.filter(Inventory.quantity <= low_stock)

    pagination = query.order_by(Inventory.quantity.asc()).paginate(page=page, per_page=50, error_out=False)

    return render_template('admin/inventory.html', pagination=pagination, search=search, low_stock=low_stock)


@admin_bp.route('/inventory/update/<int:inv_id>', methods=['POST'])
@login_required
def update_inventory(inv_id):
    admin_required()
    inv = Inventory.query.get_or_404(inv_id)
    quantity = request.form.get('quantity', type=int)
    if quantity is not None and quantity >= 0:
        old_qty = inv.quantity
        inv.quantity = quantity
        inv.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        log_action('update_inventory', 'inventory', inv_id, f'Product size {inv_id}: {old_qty} -> {quantity}')
        return jsonify({'success': True})
    return jsonify({'success': False})


# Coupons
@admin_bp.route('/coupons')
@login_required
def coupons():
    admin_required()
    page = request.args.get('page', 1, type=int)
    search = request.args.get('q', '').strip()
    status = request.args.get('status', '')

    query = Coupon.query
    if search:
        query = query.filter(Coupon.code.ilike(f'%{search}%'))
    if status == 'active':
        query = query.filter_by(is_active=True)
    elif status == 'inactive':
        query = query.filter_by(is_active=False)

    pagination = query.order_by(desc(Coupon.created_at)).paginate(page=page, per_page=20, error_out=False)
    return render_template('admin/coupons.html', pagination=pagination, search=search, status=status,
                           now=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


@admin_bp.route('/coupons/add', methods=['GET', 'POST'])
@login_required
def add_coupon():
    admin_required()
    if request.method == 'POST':
        code = request.form.get('code', '').strip().upper()
        description = request.form.get('description', '').strip()
        discount_type = request.form.get('discount_type', 'percentage')
        discount_value = request.form.get('discount_value', type=float)
        minimum_order_amount = request.form.get('minimum_order_amount', type=float, default=0)
        usage_limit = request.form.get('usage_limit', type=int)
        valid_from = request.form.get('valid_from')
        valid_to = request.form.get('valid_to')
        is_active = bool(request.form.get('is_active'))

        errors = []
        if not code: errors.append('Coupon code is required.')
        if Coupon.query.filter_by(code=code).first(): errors.append('Coupon code already exists.')
        if discount_value is None or discount_value <= 0: errors.append('Valid discount value required.')
        if discount_type == 'percentage' and discount_value > 100: errors.append('Percentage discount cannot exceed 100%.')
        if valid_from:
            try:
                valid_from = datetime.strptime(valid_from, '%Y-%m-%d')
            except ValueError:
                errors.append('Invalid valid_from date format.')
        if valid_to:
            try:
                valid_to = datetime.strptime(valid_to, '%Y-%m-%d')
            except ValueError:
                errors.append('Invalid valid_to date format.')

        if errors:
            for e in errors: flash(e, 'danger')
        else:
            coupon = Coupon(
                code=code,
                description=description,
                discount_type=discount_type,
                discount_value=discount_value,
                minimum_order_amount=minimum_order_amount,
                usage_limit=usage_limit,
                valid_from=valid_from,
                valid_to=valid_to,
                is_active=is_active
            )
            db.session.add(coupon)
            db.session.commit()
            log_action('create', 'coupon', coupon.id, f'Created coupon: {code}')
            flash('Coupon created.', 'success')
            return redirect(url_for('admin.coupons'))

    return render_template('admin/coupon_form.html', coupon=None)


@admin_bp.route('/coupons/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_coupon(id):
    admin_required()
    coupon = Coupon.query.get_or_404(id)
    if request.method == 'POST':
        coupon.code = request.form.get('code', '').strip().upper()
        coupon.description = request.form.get('description', '').strip()
        coupon.discount_type = request.form.get('discount_type', 'percentage')
        coupon.discount_value = request.form.get('discount_value', type=float)
        coupon.minimum_order_amount = request.form.get('minimum_order_amount', type=float, default=0)
        coupon.usage_limit = request.form.get('usage_limit', type=int)
        coupon.is_active = bool(request.form.get('is_active'))

        valid_from = request.form.get('valid_from')
        valid_to = request.form.get('valid_to')
        if valid_from:
            try:
                coupon.valid_from = datetime.strptime(valid_from, '%Y-%m-%d')
            except ValueError:
                flash('Invalid valid_from date format.', 'danger')
                return redirect(url_for('admin.edit_coupon', id=id))
        if valid_to:
            try:
                coupon.valid_to = datetime.strptime(valid_to, '%Y-%m-%d')
            except ValueError:
                flash('Invalid valid_to date format.', 'danger')
                return redirect(url_for('admin.edit_coupon', id=id))

        errors = []
        if not coupon.code: errors.append('Coupon code is required.')
        if Coupon.query.filter(Coupon.code == coupon.code, Coupon.id != id).first(): errors.append('Coupon code already exists.')
        if coupon.discount_value is None or coupon.discount_value <= 0: errors.append('Valid discount value required.')
        if coupon.discount_type == 'percentage' and coupon.discount_value > 100: errors.append('Percentage discount cannot exceed 100%.')

        if errors:
            for e in errors: flash(e, 'danger')
        else:
            db.session.commit()
            log_action('update', 'coupon', coupon.id, f'Updated coupon: {coupon.code}')
            flash('Coupon updated.', 'success')
            return redirect(url_for('admin.coupons'))

    return render_template('admin/coupon_form.html', coupon=coupon)


@admin_bp.route('/coupons/delete/<int:id>', methods=['POST'])
@login_required
def delete_coupon(id):
    admin_required()
    coupon = Coupon.query.get_or_404(id)
    code = coupon.code
    db.session.delete(coupon)
    db.session.commit()
    log_action('delete', 'coupon', id, f'Deleted coupon: {code}')
    flash('Coupon deleted.', 'success')
    return redirect(url_for('admin.coupons'))


# Reviews
@admin_bp.route('/reviews')
@login_required
def reviews():
    admin_required()
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', 'pending')
    search = request.args.get('q', '').strip()

    query = Review.query.join(Product).join(Customer)
    if status == 'pending':
        query = query.filter(Review.is_approved == False)  # noqa: E712
    elif status == 'approved':
        query = query.filter(Review.is_approved == True)  # noqa: E712
    if search:
        query = query.filter(or_(
            Product.name.ilike(f'%{search}%'),
            Customer.name.ilike(f'%{search}%')
        ))

    pagination = query.order_by(desc(Review.created_at)).paginate(page=page, per_page=20, error_out=False)
    return render_template('admin/reviews.html', pagination=pagination, status=status, search=search)


@admin_bp.route('/reviews/<int:id>/approve', methods=['POST'])
@login_required
def approve_review(id):
    admin_required()
    review = Review.query.get_or_404(id)
    review.is_approved = True
    db.session.commit()
    log_action('approve', 'review', id, f'Approved review for product {review.product_id}')
    return jsonify({'success': True})


@admin_bp.route('/reviews/<int:id>/reject', methods=['POST'])
@login_required
def reject_review(id):
    admin_required()
    review = Review.query.get_or_404(id)
    db.session.delete(review)
    db.session.commit()
    log_action('reject', 'review', id, f'Rejected review for product {review.product_id}')
    return jsonify({'success': True})


# Settings
@admin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    admin_required()
    # For now just render template - actual settings would be stored in DB or config
    return render_template('admin/settings.html')


SITE_IMAGES = {
    # key: (label, max width, max height)
    'hero': ('Homepage banner', 2400, 1600),
    'about': ('"Our Story" photo', 1400, 1750),
}


@admin_bp.route('/settings/site-images', methods=['POST'])
@login_required
def update_site_images():
    """Upload / remove the homepage banner and 'Our Story' photos."""
    admin_required()
    from PIL import Image, ImageOps

    folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'site')
    os.makedirs(folder, exist_ok=True)

    remove_key = request.form.get('remove')
    if remove_key in SITE_IMAGES:
        path = os.path.join(folder, f'{remove_key}.jpg')
        if os.path.exists(path):
            os.remove(path)
        flash(f'{SITE_IMAGES[remove_key][0]} removed. The default design is shown again.', 'success')
        return redirect(url_for('admin.settings'))

    saved, failed = [], False
    for key, (label, max_w, max_h) in SITE_IMAGES.items():
        file = request.files.get(key)
        if not file or not file.filename:
            continue
        try:
            img = Image.open(file.stream)
            img = ImageOps.exif_transpose(img)  # respect phone photo rotation
            img = img.convert('RGB')
            img.thumbnail((max_w, max_h), Image.LANCZOS)
            img.save(os.path.join(folder, f'{key}.jpg'), 'JPEG', quality=85, optimize=True, progressive=True)
            saved.append(label)
        except Exception as exc:  # noqa: BLE001
            current_app.logger.warning('Site image upload failed for %s: %s', key, exc)
            flash(f'Could not use that file for the {label}. Please upload a JPG or PNG photo.', 'danger')
            failed = True

    if saved:
        db.session.add(AuditLog(admin_id=current_user.id, action='update', resource_type='site_images',
                                resource_id=','.join(saved), ip_address=request.remote_addr))
        db.session.commit()
        flash(f'Updated: {", ".join(saved)}. Check your homepage!', 'success')
    elif not failed:
        flash('Please choose a photo to upload.', 'warning')
    return redirect(url_for('admin.settings'))


# Audit Logs
@admin_bp.route('/audit-logs')
@login_required
def audit_logs():
    admin_required()
    page = request.args.get('page', 1, type=int)
    search = request.args.get('q', '').strip()

    query = AuditLog.query.join(Admin, AuditLog.admin_id == Admin.id, isouter=True)
    if search:
        query = query.filter(or_(
            AuditLog.action.ilike(f'%{search}%'),
            AuditLog.resource_type.ilike(f'%{search}%'),
            Admin.name.ilike(f'%{search}%'),
            Admin.email.ilike(f'%{search}%')
        ))

    pagination = query.order_by(desc(AuditLog.created_at)).paginate(page=page, per_page=50, error_out=False)
    return render_template('admin/audit_logs.html', pagination=pagination, search=search)


def _order_images(order):
    """product_id -> image filename (primary first) for showing thumbnails on order pages."""
    from ..models import ProductImage
    ids = {item.product_id for item in order.items if item.product_id}
    if not ids:
        return {}
    images = {}
    rows = ProductImage.query.filter(ProductImage.product_id.in_(ids)) \
        .order_by(ProductImage.is_primary.desc(), ProductImage.id).all()
    for img in rows:
        images.setdefault(img.product_id, img.image_filename)
    return images
