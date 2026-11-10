from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from sqlalchemy import or_, desc, func

from ..extensions import db
from ..models import (
    Product, ProductImage, ProductSize, Inventory, Category,
    Cart, CartItem, Wishlist, WishlistItem, NewsletterSubscriber,
    CustomerAddress, Order, OrderItem, Coupon, Review
)
from ..services.order_service import OrderService

api_bp = Blueprint('api', __name__)


# ============ Products ============
@api_bp.route('/products')
def get_products():
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 12, type=int), 50)
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
        query = query.join(Product.sizes).join(ProductSize.inventory).filter(
            ProductSize.size_label == size,
            Inventory.quantity > 0
        ).distinct()

    if sort == 'price_low':
        query = query.order_by(Product.discounted_price.asc())
    elif sort == 'price_high':
        query = query.order_by(Product.discounted_price.desc())
    elif sort == 'popular':
        query = query.order_by(Product.created_at.desc())
    else:
        query = query.order_by(Product.created_at.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    products_data = []
    for p in pagination.items:
        primary_img = ProductImage.query.filter_by(product_id=p.id, is_primary=True).first()
        if not primary_img:
            primary_img = ProductImage.query.filter_by(product_id=p.id).first()

        products_data.append({
            'id': p.id,
            'name': p.name,
            'description': p.description,
            'original_price': float(p.original_price),
            'discounted_price': float(p.discounted_price),
            'image': primary_img.image_filename if primary_img else None,
            'category_id': p.category_id,
            'is_featured': p.is_featured,
            'avg_rating': p.get_average_rating(),
            'review_count': p.get_review_count(),
        })

    return jsonify({
        'products': products_data,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': pagination.page
    })


@api_bp.route('/products/<int:id>')
def get_product(id):
    product = Product.query.filter_by(id=id, is_active=True).first_or_404()

    images = ProductImage.query.filter_by(product_id=id).all()
    sizes = ProductSize.query.filter_by(product_id=id).all()
    reviews = Review.query.filter_by(product_id=id, is_approved=True).order_by(desc(Review.created_at)).all()

    inventory_map = {}
    for s in sizes:
        inv = Inventory.query.filter_by(product_size_id=s.id).first()
        inventory_map[s.size_label] = inv.quantity if inv else 0

    return jsonify({
        'id': product.id,
        'name': product.name,
        'description': product.description,
        'original_price': float(product.original_price),
        'discounted_price': float(product.discounted_price),
        'category_id': product.category_id,
        'is_featured': product.is_featured,
        'images': [img.image_filename for img in images],
        'sizes': [
            {
                'id': s.id,
                'label': s.size_label,
                'stock': inventory_map.get(s.size_label, 0)
            }
            for s in sizes
        ],
        'reviews': [
            {
                'id': r.id,
                'customer_name': r.customer.name,
                'rating': r.rating,
                'comment': r.comment,
                'created_at': r.created_at.isoformat()
            }
            for r in reviews
        ],
        'avg_rating': product.get_average_rating(),
        'review_count': product.get_review_count(),
    })


# ============ Categories ============
@api_bp.route('/categories')
def get_categories():
    categories = Category.query.filter_by(is_active=True).order_by(Category.name).all()
    return jsonify({
        'categories': [
            {
                'id': c.id,
                'name': c.name,
                'description': c.description,
                'image': c.image_filename,
                'product_count': Product.query.filter_by(category_id=c.id, is_active=True).count()
            }
            for c in categories
        ]
    })


# ============ Cart ============
@api_bp.route('/cart')
@login_required
def get_cart():
    cart = Cart.query.filter_by(customer_id=current_user.id).first()
    if not cart:
        return jsonify({'items': [], 'subtotal': 0, 'shipping': 0, 'total': 0, 'count': 0})

    items = []
    subtotal = 0
    for item in cart.items:
        p = db.session.get(Product, item.product_id)
        s = db.session.get(ProductSize, item.product_size_id)
        if p and p.is_active:
            primary_img = ProductImage.query.filter_by(product_id=p.id, is_primary=True).first()
            if not primary_img:
                primary_img = ProductImage.query.filter_by(product_id=p.id).first()
            line_total = float(p.discounted_price) * item.quantity
            subtotal += line_total
            items.append({
                'id': item.id,
                'product_id': p.id,
                'product_name': p.name,
                'size_id': s.id,
                'size_label': s.size_label,
                'price': float(p.discounted_price),
                'quantity': item.quantity,
                'line_total': line_total,
                'image': primary_img.image_filename if primary_img else None,
            })

    shipping = 0 if subtotal >= 1000 else 50
    total = subtotal + shipping

    return jsonify({
        'items': items,
        'subtotal': subtotal,
        'shipping': shipping,
        'total': total,
        'count': len(items)
    })


@api_bp.route('/cart/add', methods=['POST'])
@login_required
def api_add_to_cart():
    data = request.get_json()
    product_id = data.get('product_id')
    size_id = data.get('size_id')
    quantity = data.get('quantity', 1)

    if not product_id or not size_id:
        return jsonify({'success': False, 'message': 'Product ID and Size ID required'}), 400

    product = Product.query.get_or_404(product_id)
    size = ProductSize.query.get_or_404(size_id)

    inv = Inventory.query.filter_by(product_size_id=size_id).first()
    if not inv or inv.quantity < quantity:
        return jsonify({'success': False, 'message': 'Insufficient stock'}), 400

    cart = Cart.query.filter_by(customer_id=current_user.id).first()
    if not cart:
        cart = Cart(customer_id=current_user.id)
        db.session.add(cart)
        db.session.flush()

    cart_item = CartItem.query.filter_by(
        cart_id=cart.id,
        product_id=product_id,
        product_size_id=size_id
    ).first()

    if cart_item:
        cart_item.quantity += quantity
    else:
        cart_item = CartItem(
            cart_id=cart.id,
            product_id=product_id,
            product_size_id=size_id,
            quantity=quantity
        )
        db.session.add(cart_item)

    db.session.commit()
    return jsonify({'success': True, 'message': 'Added to cart'})


@api_bp.route('/cart/update', methods=['POST'])
@login_required
def api_update_cart():
    data = request.get_json()
    item_id = data.get('item_id')
    quantity = data.get('quantity')

    if not item_id or quantity is None:
        return jsonify({'success': False, 'message': 'Item ID and quantity required'}), 400

    cart_item = CartItem.query.get_or_404(item_id)
    if cart_item.cart.customer_id != current_user.id:
        return jsonify({'success': False}), 403

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


@api_bp.route('/cart/remove/<int:item_id>', methods=['POST'])
@login_required
def api_remove_from_cart(item_id):
    cart_item = CartItem.query.get_or_404(item_id)
    if cart_item.cart.customer_id != current_user.id:
        return jsonify({'success': False}), 403

    db.session.delete(cart_item)
    db.session.commit()
    return jsonify({'success': True})


@api_bp.route('/cart/clear', methods=['POST'])
@login_required
def api_clear_cart():
    cart = Cart.query.filter_by(customer_id=current_user.id).first()
    if cart:
        CartItem.query.filter_by(cart_id=cart.id).delete()
        db.session.commit()
    return jsonify({'success': True})


@api_bp.route('/cart/apply-coupon', methods=['POST'])
@login_required
def api_apply_coupon():
    data = request.get_json()
    code = data.get('code', '').strip().upper()

    if not code:
        return jsonify({'success': False, 'message': 'Coupon code required'})

    cart = Cart.query.filter_by(customer_id=current_user.id).first()
    if not cart or not cart.items:
        return jsonify({'success': False, 'message': 'Cart is empty'})

    subtotal = 0
    for item in cart.items:
        p = db.session.get(Product, item.product_id)
        if p and p.is_active:
            subtotal += float(p.discounted_price) * item.quantity

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


# ============ Wishlist ============
@api_bp.route('/wishlist')
@login_required
def get_wishlist():
    wl = Wishlist.query.filter_by(customer_id=current_user.id).first()
    products = []
    if wl:
        for item in wl.items:
            p = db.session.get(Product, item.product_id)
            if p and p.is_active:
                primary_img = ProductImage.query.filter_by(product_id=p.id, is_primary=True).first()
                if not primary_img:
                    primary_img = ProductImage.query.filter_by(product_id=p.id).first()
                products.append({
                    'id': p.id,
                    'name': p.name,
                    'discounted_price': float(p.discounted_price),
                    'image': primary_img.image_filename if primary_img else None,
                    'avg_rating': p.get_average_rating(),
                })
    return jsonify({'products': products, 'count': len(products)})


@api_bp.route('/wishlist/toggle', methods=['POST'])
@login_required
def api_toggle_wishlist():
    data = request.get_json()
    product_id = data.get('product_id')

    if not product_id:
        return jsonify({'success': False, 'message': 'Product ID required'}), 400

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


@api_bp.route('/wishlist/remove/<int:product_id>', methods=['POST'])
@login_required
def api_remove_from_wishlist(product_id):
    wl = Wishlist.query.filter_by(customer_id=current_user.id).first()
    if not wl:
        return jsonify({'success': False, 'message': 'Wishlist not found'}), 404

    item = WishlistItem.query.filter_by(wishlist_id=wl.id, product_id=product_id).first()
    if item:
        db.session.delete(item)
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Item not in wishlist'}), 404


# ============ Newsletter ============
@api_bp.route('/newsletter/subscribe', methods=['POST'])
def api_newsletter_subscribe():
    data = request.get_json()
    email = data.get('email', '').strip().lower()

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


@api_bp.route('/newsletter/unsubscribe', methods=['POST'])
def api_newsletter_unsubscribe():
    data = request.get_json()
    email = data.get('email', '').strip().lower()

    existing = NewsletterSubscriber.query.filter_by(email=email).first()
    if existing:
        existing.is_active = False
        db.session.commit()
    return jsonify({'success': True, 'message': 'Unsubscribed'})


# ============ Orders ============
@api_bp.route('/orders')
@login_required
def get_orders():
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 10, type=int), 50)

    pagination = Order.query.filter_by(customer_id=current_user.id)\
        .order_by(desc(Order.created_at))\
        .paginate(page=page, per_page=per_page, error_out=False)

    orders_data = []
    for order in pagination.items:
        orders_data.append({
            'id': order.id,
            'order_number': order.order_number,
            'status': order.status,
            'payment_status': order.payment_status,
            'payment_method': order.payment_method,
            'total_amount': float(order.total_amount),
            'created_at': order.created_at.isoformat(),
            'items_count': len(order.items)
        })

    return jsonify({
        'orders': orders_data,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': pagination.page
    })


@api_bp.route('/orders/<int:id>')
@login_required
def get_order(id):
    order = Order.query.filter_by(id=id, customer_id=current_user.id).first_or_404()
    summary = OrderService.get_order_summary(order)
    return jsonify(summary)


# ============ Customer Addresses ============
@api_bp.route('/addresses')
@login_required
def get_addresses():
    addresses = CustomerAddress.query.filter_by(customer_id=current_user.id).all()
    return jsonify({
        'addresses': [
            {
                'id': a.id,
                'name': a.name,
                'phone': a.phone,
                'address_line': a.address_line,
                'city': a.city,
                'state': a.state,
                'pincode': a.pincode,
                'is_default': a.is_default
            }
            for a in addresses
        ]
    })


@api_bp.route('/addresses', methods=['POST'])
@login_required
def add_address():
    data = request.get_json()
    required = ['name', 'phone', 'address_line', 'city', 'state', 'pincode']
    for field in required:
        if not data.get(field):
            return jsonify({'success': False, 'message': f'{field} is required'}), 400

    if data.get('is_default'):
        CustomerAddress.query.filter_by(customer_id=current_user.id, is_default=True).update({'is_default': False})

    addr = CustomerAddress(
        customer_id=current_user.id,
        name=data['name'],
        phone=data['phone'],
        address_line=data['address_line'],
        city=data['city'],
        state=data['state'],
        pincode=data['pincode'],
        is_default=data.get('is_default', False)
    )
    db.session.add(addr)
    db.session.commit()
    return jsonify({'success': True, 'id': addr.id})


@api_bp.route('/addresses/<int:id>', methods=['DELETE'])
@login_required
def delete_address(id):
    addr = CustomerAddress.query.filter_by(id=id, customer_id=current_user.id).first_or_404()
    db.session.delete(addr)
    db.session.commit()
    return jsonify({'success': True})


# ============ Reviews ============
@api_bp.route('/products/<int:id>/reviews')
def get_product_reviews(id):
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 10, type=int), 50)

    pagination = Review.query.filter_by(product_id=id, is_approved=True)\
        .order_by(desc(Review.created_at))\
        .paginate(page=page, per_page=per_page, error_out=False)

    reviews_data = []
    for r in pagination.items:
        reviews_data.append({
            'id': r.id,
            'customer_name': r.customer.name,
            'rating': r.rating,
            'comment': r.comment,
            'created_at': r.created_at.isoformat()
        })

    product = Product.query.get_or_404(id)
    return jsonify({
        'reviews': reviews_data,
        'total': pagination.total,
        'pages': pagination.pages,
        'avg_rating': product.get_average_rating(),
        'review_count': product.get_review_count()
    })


@api_bp.route('/products/<int:id>/reviews', methods=['POST'])
@login_required
def api_add_review(id):
    product = Product.query.filter_by(id=id, is_active=True).first_or_404()

    existing = Review.query.filter_by(customer_id=current_user.id, product_id=id).first()
    if existing:
        return jsonify({'success': False, 'message': 'Already reviewed'}), 400

    data = request.get_json()
    rating = data.get('rating')
    comment = data.get('comment', '').strip()

    if not rating or rating < 1 or rating > 5:
        return jsonify({'success': False, 'message': 'Rating must be 1-5'}), 400

    review = Review(
        customer_id=current_user.id,
        product_id=id,
        rating=rating,
        comment=comment,
        is_approved=False
    )
    db.session.add(review)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Review submitted for approval'})


# ============ Coupons ============
@api_bp.route('/coupons/validate', methods=['POST'])
@login_required
def api_validate_coupon():
    data = request.get_json()
    code = data.get('code', '').strip().upper()
    subtotal = data.get('subtotal', 0)

    if not code:
        return jsonify({'success': False, 'message': 'Coupon code required'})

    is_valid, msg, coupon = OrderService.validate_coupon(code, subtotal)
    if not is_valid:
        return jsonify({'success': False, 'message': msg})

    return jsonify({
        'success': True,
        'coupon': {
            'code': coupon.code,
            'discount_type': coupon.discount_type,
            'discount_value': float(coupon.discount_value),
            'discount_amount': coupon.calculate_discount(subtotal)
        }
    })


# ============ Search/Suggestions ============
@api_bp.route('/search/suggestions')
def search_suggestions():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify({'suggestions': []})

    products = Product.query.filter(
        Product.is_active == True,
        Product.name.ilike(f'%{q}%')
    ).limit(10).all()

    return jsonify({
        'suggestions': [
            {
                'id': p.id,
                'name': p.name,
                'price': float(p.discounted_price)
            }
            for p in products
        ]
    })