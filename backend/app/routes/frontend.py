from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from sqlalchemy import or_, desc, asc, func
from datetime import datetime, timezone

from ..extensions import db
from ..models import (
    Category, Product, ProductImage, ProductSize, Inventory,
    Cart, CartItem, Wishlist, WishlistItem, Order, OrderItem,
    NewsletterSubscriber, CustomerAddress, Coupon, Review
)
from ..services.order_service import OrderService

frontend_bp = Blueprint('frontend', __name__)


@frontend_bp.route('/')
def index():
    # Hero data
    featured_products = Product.query.filter_by(is_active=True, is_featured=True).limit(8).all()
    new_arrivals = Product.query.filter_by(is_active=True).order_by(desc(Product.created_at)).limit(8).all()
    categories = Category.query.filter_by(is_active=True).all()

    # Get primary images for products
    for p in featured_products + new_arrivals:
        primary_img = ProductImage.query.filter_by(product_id=p.id, is_primary=True).first()
        if not primary_img:
            primary_img = ProductImage.query.filter_by(product_id=p.id).first()
        p.primary_image = primary_img.image_filename if primary_img else None

    return render_template('frontend/index.html',
                           featured_products=featured_products,
                           new_arrivals=new_arrivals,
                           categories=categories)


@frontend_bp.route('/shop')
def shop():
    page = request.args.get('page', 1, type=int)
    per_page = 12
    category_id = request.args.get('category', type=int)
    search = request.args.get('q', '').strip()
    sort = request.args.get('sort', 'newest')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    size = request.args.get('size', '').strip()

    query = Product.query.filter_by(is_active=True)

    if category_id:
        query = query.filter_by(category_id=category_id)

    if search:
        query = query.filter(or_(
            Product.name.ilike(f'%{search}%'),
            Product.description.ilike(f'%{search}%')
        ))

    if min_price is not None:
        query = query.filter(Product.discounted_price >= min_price)
    if max_price is not None:
        query = query.filter(Product.discounted_price <= max_price)

    if size:
        # Join with inventory and product_sizes
        query = query.join(Product.sizes).join(ProductSize.inventory).filter(
            ProductSize.size_label == size,
            Inventory.quantity > 0
        ).distinct()

    if sort == 'price_low':
        query = query.order_by(asc(Product.discounted_price))
    elif sort == 'price_high':
        query = query.order_by(desc(Product.discounted_price))
    elif sort == 'popular':
        query = query.order_by(desc(Product.created_at))
    else:
        query = query.order_by(desc(Product.created_at))

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    products = pagination.items

    # Add primary images and ratings
    for p in products:
        primary_img = ProductImage.query.filter_by(product_id=p.id, is_primary=True).first()
        if not primary_img:
            primary_img = ProductImage.query.filter_by(product_id=p.id).first()
        p.primary_image = primary_img.image_filename if primary_img else None
        p.avg_rating = p.get_average_rating()
        p.review_count = p.get_review_count()

    categories = Category.query.filter_by(is_active=True).all()

    return render_template('frontend/shop.html',
                           products=products,
                           pagination=pagination,
                           categories=categories,
                           current_category=category_id,
                           search=search,
                           sort=sort,
                           min_price=min_price,
                           max_price=max_price,
                           size=size)


@frontend_bp.route('/product/<int:id>')
def product_detail(id):
    product = db.session.get(Product, id)
    if not product or not product.is_active:
        from flask import abort
        abort(404)

    images = ProductImage.query.filter_by(product_id=id).all()
    sizes = ProductSize.query.filter_by(product_id=id).all()

    # Get inventory for each size
    inventory_map = {}
    for s in sizes:
        inv = Inventory.query.filter_by(product_size_id=s.id).first()
        inventory_map[s.id] = inv.quantity if inv else 0

    # Reviews
    reviews = Review.query.filter_by(product_id=id, is_approved=True).order_by(desc(Review.created_at)).all()

    # Related products (same category)
    related = Product.query.filter(
        Product.category_id == product.category_id,
        Product.id != product.id,
        Product.is_active == True
    ).limit(4).all()
    for p in related:
        primary_img = ProductImage.query.filter_by(product_id=p.id, is_primary=True).first()
        if not primary_img:
            primary_img = ProductImage.query.filter_by(product_id=p.id).first()
        p.primary_image = primary_img.image_filename if primary_img else None
        p.avg_rating = p.get_average_rating()
        p.review_count = p.get_review_count()

    return render_template('frontend/product_detail.html',
                           product=product,
                           images=images,
                           sizes=sizes,
                           inventory_map=inventory_map,
                           reviews=reviews,
                           avg_rating=product.get_average_rating(),
                           review_count=product.get_review_count(),
                           related_products=related)


@frontend_bp.route('/product/<int:id>/review', methods=['POST'])
@login_required
def add_review(id):
    product = Product.query.filter_by(id=id, is_active=True).first_or_404()

    # Check if customer already reviewed
    existing = Review.query.filter_by(customer_id=current_user.id, product_id=id).first()
    if existing:
        flash('You have already reviewed this product.', 'warning')
        return redirect(url_for('frontend.product_detail', id=id))

    rating = request.form.get('rating', type=int)
    comment = request.form.get('comment', '').strip()

    if not rating or rating < 1 or rating > 5:
        flash('Please select a rating.', 'danger')
        return redirect(url_for('frontend.product_detail', id=id))

    review = Review(
        customer_id=current_user.id,
        product_id=id,
        rating=rating,
        comment=comment,
        is_approved=False  # Requires admin approval
    )
    db.session.add(review)
    db.session.commit()

    flash('Review submitted for approval.', 'success')
    return redirect(url_for('frontend.product_detail', id=id))


@frontend_bp.route('/cart')
@login_required
def cart():
    cart_obj = Cart.query.filter_by(customer_id=current_user.id).first()
    items = []
    subtotal = 0
    if cart_obj:
        for item in cart_obj.items:
            p = db.session.get(Product, item.product_id)
            s = db.session.get(ProductSize, item.product_size_id)
            if p and p.is_active:
                item.product = p
                item.size = s
                item.line_total = float(p.discounted_price) * item.quantity
                subtotal += item.line_total
                items.append(item)

    product_images = {}
    if cart_obj:
        for item in cart_obj.items:
            p = db.session.get(Product, item.product_id)
            if p and p.is_active:
                primary_img = ProductImage.query.filter_by(product_id=p.id, is_primary=True).first()
                if not primary_img:
                    primary_img = ProductImage.query.filter_by(product_id=p.id).first()
                product_images[p.id] = primary_img.image_filename if primary_img else None

    shipping = 0 if subtotal >= 1000 else 50
    total = subtotal + shipping

    return render_template('frontend/cart.html',
                           items=items,
                           subtotal=subtotal,
                           product_images=product_images,
                           shipping=shipping,
                           total=total)


@frontend_bp.route('/cart/add', methods=['POST'])
@login_required
def add_to_cart():
    product_id = request.form.get('product_id', type=int)
    size_id = request.form.get('size_id', type=int)
    quantity = request.form.get('quantity', 1, type=int)

    product = Product.query.get_or_404(product_id)
    size = ProductSize.query.get_or_404(size_id)

    # Check stock
    inv = Inventory.query.filter_by(product_size_id=size_id).first()
    if not inv or inv.quantity < quantity:
        return jsonify({'success': False, 'message': 'Insufficient stock'}), 400

    # Get or create cart
    cart_obj = Cart.query.filter_by(customer_id=current_user.id).first()
    if not cart_obj:
        cart_obj = Cart(customer_id=current_user.id)
        db.session.add(cart_obj)
        db.session.flush()

    # Check existing item
    cart_item = CartItem.query.filter_by(
        cart_id=cart_obj.id,
        product_id=product_id,
        product_size_id=size_id
    ).first()

    if cart_item:
        cart_item.quantity += quantity
    else:
        cart_item = CartItem(
            cart_id=cart_obj.id,
            product_id=product_id,
            product_size_id=size_id,
            quantity=quantity
        )
        db.session.add(cart_item)

    db.session.commit()
    return jsonify({'success': True, 'message': 'Added to cart'})


@frontend_bp.route('/cart/update', methods=['POST'])
@login_required
def update_cart():
    item_id = request.form.get('item_id', type=int)
    quantity = request.form.get('quantity', type=int)

    cart_item = CartItem.query.get_or_404(item_id)
    if cart_item.cart.customer_id != current_user.id:
        return jsonify({'success': False}), 403

    # Check stock
    inv = Inventory.query.filter_by(product_size_id=cart_item.product_size_id).first()
    if not inv or inv.quantity < quantity:
        return jsonify({'success': False, 'message': 'Insufficient stock'}), 400

    if quantity > 0:
        cart_item.quantity = quantity
        db.session.commit()
        return jsonify({'success': True})
    else:
        db.session.delete(cart_item)
        db.session.commit()
        return jsonify({'success': True, 'removed': True})


@frontend_bp.route('/cart/remove/<int:item_id>', methods=['POST'])
@login_required
def remove_from_cart(item_id):
    cart_item = CartItem.query.get_or_404(item_id)
    if cart_item.cart.customer_id != current_user.id:
        return jsonify({'success': False}), 403

    db.session.delete(cart_item)
    db.session.commit()
    return jsonify({'success': True})


@frontend_bp.route('/cart/apply-coupon', methods=['POST'])
@login_required
def apply_coupon():
    """Apply coupon to cart."""
    code = request.form.get('code', '').strip().upper()
    if not code:
        return jsonify({'success': False, 'message': 'Coupon code required'})

    cart_obj = Cart.query.filter_by(customer_id=current_user.id).first()
    if not cart_obj or not cart_obj.items:
        return jsonify({'success': False, 'message': 'Cart is empty'})

    # Calculate subtotal
    subtotal = 0
    for item in cart_obj.items:
        p = db.session.get(Product, item.product_id)
        if p and p.is_active:
            subtotal += float(p.discounted_price) * item.quantity

    # Validate coupon
    is_valid, msg, coupon = OrderService.validate_coupon(code, subtotal)
    if not is_valid:
        return jsonify({'success': False, 'message': msg})

    discount = coupon.calculate_discount(subtotal)
    shipping = 0 if subtotal >= 1000 else 50
    total = subtotal + shipping - discount

    return jsonify({
        'success': True,
        'message': 'Coupon applied',
        'discount': discount,
        'subtotal': subtotal,
        'shipping': shipping,
        'total': total,
        'coupon_code': coupon.code
    })


@frontend_bp.route('/wishlist')
@login_required
def wishlist():
    wl = Wishlist.query.filter_by(customer_id=current_user.id).first()
    products = []
    if wl:
        for item in wl.items:
            p = db.session.get(Product, item.product_id)
            if p and p.is_active:
                primary_img = ProductImage.query.filter_by(product_id=p.id, is_primary=True).first()
                if not primary_img:
                    primary_img = ProductImage.query.filter_by(product_id=p.id).first()
                p.primary_image = primary_img.image_filename if primary_img else None
                p.avg_rating = p.get_average_rating()
                p.review_count = p.get_review_count()
                products.append(p)
    return render_template('frontend/wishlist.html', products=products)


@frontend_bp.route('/wishlist/toggle', methods=['POST'])
@login_required
def toggle_wishlist():
    product_id = request.form.get('product_id', type=int)

    wl = Wishlist.query.filter_by(customer_id=current_user.id).first()
    if not wl:
        wl = Wishlist(customer_id=current_user.id)
        db.session.add(wl)
        db.session.flush()

    existing = WishlistItem.query.filter_by(wishlist_id=wl.id, product_id=product_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({'success': True, 'in_wishlist': False})
    else:
        db.session.add(WishlistItem(wishlist_id=wl.id, product_id=product_id))
        db.session.commit()
        return jsonify({'success': True, 'in_wishlist': True})


@frontend_bp.route('/checkout')
@login_required
def checkout():
    """Redirect to payment checkout."""
    return redirect(url_for('payment.checkout'))


@frontend_bp.route('/order/confirmation/<int:order_id>')
@login_required
def order_confirmation(order_id):
    order = Order.query.filter_by(id=order_id, customer_id=current_user.id).first_or_404()
    return render_template('frontend/order_confirmation.html', order=order)


@frontend_bp.route('/orders')
@login_required
def orders():
    page = request.args.get('page', 1, type=int)
    pagination = Order.query.filter_by(customer_id=current_user.id)\
        .order_by(desc(Order.created_at))\
        .paginate(page=page, per_page=10, error_out=False)
    return render_template('frontend/orders.html', pagination=pagination)


@frontend_bp.route('/order/<int:order_id>')
@login_required
def order_detail(order_id):
    order = Order.query.filter_by(id=order_id, customer_id=current_user.id).first_or_404()
    return render_template('frontend/order_detail.html', order=order, order_images=_order_images(order))


@frontend_bp.route('/account')
@login_required
def account():
    addresses = CustomerAddress.query.filter_by(customer_id=current_user.id).all()
    # Get recent orders for account page
    recent_orders = Order.query.filter_by(customer_id=current_user.id)\
        .order_by(desc(Order.created_at)).limit(5).all()
    return render_template('frontend/account.html', addresses=addresses, recent_orders=recent_orders)


@frontend_bp.route('/account/update', methods=['POST'])
@login_required
def update_account():
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()

    if not name:
        flash('Name is required.', 'danger')
    else:
        current_user.name = name
        current_user.phone = phone
        db.session.commit()
        flash('Profile updated.', 'success')
    return redirect(url_for('frontend.account'))


@frontend_bp.route('/account/address/add', methods=['POST'])
@login_required
def add_address():
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    address = request.form.get('address', '').strip()
    city = request.form.get('city', '').strip()
    state = request.form.get('state', '').strip()
    pincode = request.form.get('pincode', '').strip()
    is_default = bool(request.form.get('is_default'))

    if not all([name, phone, address, city, state, pincode]):
        flash('All fields are required.', 'danger')
        return redirect(url_for('frontend.account'))

    if is_default:
        CustomerAddress.query.filter_by(customer_id=current_user.id, is_default=True).update({'is_default': False})

    addr = CustomerAddress(
        customer_id=current_user.id,
        name=name,
        phone=phone,
        address_line=address,
        city=city,
        state=state,
        pincode=pincode,
        is_default=is_default
    )
    db.session.add(addr)
    db.session.commit()
    flash('Address added.', 'success')
    return redirect(url_for('frontend.account'))


@frontend_bp.route('/account/address/delete/<int:address_id>', methods=['POST'])
@login_required
def delete_address(address_id):
    addr = CustomerAddress.query.filter_by(id=address_id, customer_id=current_user.id).first_or_404()
    db.session.delete(addr)
    db.session.commit()
    flash('Address deleted.', 'success')
    return redirect(url_for('frontend.account'))


@frontend_bp.route('/newsletter/subscribe', methods=['POST'])
def newsletter_subscribe():
    email = request.form.get('email', '').strip().lower()
    if not email or '@' not in email:
        return jsonify({'success': False, 'message': 'Invalid email'})

    existing = NewsletterSubscriber.query.filter_by(email=email).first()
    if existing:
        if not existing.is_active:
            existing.is_active = True
            db.session.commit()
        return jsonify({'success': True, 'message': 'Already subscribed'})

    sub = NewsletterSubscriber(email=email)
    db.session.add(sub)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Subscribed successfully'})


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
