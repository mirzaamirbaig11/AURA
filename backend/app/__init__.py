import os
from flask import Flask
from .config import config
from .extensions import db, migrate, login_manager, csrf, limiter, mail, stripe_imported
from .models import *  # noqa: F401,F403

def create_app(config_name='default'):
    # CSS/JS/images/uploads live in <project>/frontend/static
    static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'frontend', 'static')
    app = Flask(__name__, static_folder=static_dir, static_url_path='/static')
    # Behind Cloudflare Tunnel / Render: use the public https URL in generated links
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    app.config.from_object(config[config_name])

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    mail.init_app(app)

    # Initialize Stripe only when online payments are enabled and keys are configured
    if app.config.get('ENABLE_ONLINE_PAYMENT') and stripe_imported:
        import stripe as _stripe
        _stripe.api_key = app.config.get('STRIPE_SECRET_KEY')

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'

    # Register blueprints
    from .routes.auth import auth_bp
    from .routes.frontend import frontend_bp
    from .routes.admin import admin_bp
    from .routes.api import api_bp
    from .routes.payment import payment_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(frontend_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(payment_bp, url_prefix='/payment')

    # Template context processors
    @app.context_processor
    def inject_config():
        return dict(config=app.config)

    @app.context_processor
    def inject_nav_categories():
        # Categories for the navbar dropdown on every page (templates can still override)
        try:
            from .models import Category
            cats = Category.query.filter_by(is_active=True).order_by(Category.name).all()
        except Exception:  # noqa: BLE001 - DB not ready (e.g. during migrations)
            cats = []
        return dict(nav_categories=cats)

    @app.context_processor
    def inject_site_images():
        # Homepage photos uploaded from Admin > Settings (None = use the default design)
        folder = os.path.join(app.config['UPLOAD_FOLDER'], 'site')
        images = {}
        for key in ('hero', 'about'):
            path = os.path.join(folder, f'{key}.jpg')
            if os.path.exists(path):
                images[key] = f"/static/uploads/site/{key}.jpg?v={int(os.path.getmtime(path))}"
            else:
                images[key] = None
        return dict(site_images=images)

    @app.template_filter('inr')
    def format_inr(value):
        """1499 -> '1,499' ; 124999.5 -> '1,24,999.50' (Indian digit grouping)."""
        try:
            amount = float(value or 0)
        except (TypeError, ValueError):
            return value
        negative = amount < 0
        amount = abs(amount)
        rupees = int(amount)
        paise = round((amount - rupees) * 100)
        if paise == 100:
            rupees, paise = rupees + 1, 0
        digits = str(rupees)
        if len(digits) > 3:
            head, tail = digits[:-3], digits[-3:]
            groups = []
            while len(head) > 2:
                groups.insert(0, head[-2:])
                head = head[:-2]
            if head:
                groups.insert(0, head)
            digits = ','.join(groups) + ',' + tail
        text = digits + (f'.{paise:02d}' if paise else '')
        return ('-' if negative else '') + text

    @app.context_processor
    def inject_stripe_key():
        # Only expose Stripe key when online payment is enabled
        if app.config.get('ENABLE_ONLINE_PAYMENT'):
            return dict(stripe_publishable_key=app.config.get('STRIPE_PUBLISHABLE_KEY'))
        return {}

    # Friendly error pages
    from flask import render_template as _rt

    def _error_page(code, title, message):
        try:
            return _rt('error.html', code=code, title=title, message=message), code
        except Exception:  # noqa: BLE001 - never fail while rendering an error
            return f'<h1>{code} {title}</h1><p>{message}</p>', code

    @app.errorhandler(404)
    def not_found(e):
        return _error_page(404, 'Page not found', "The page you're looking for doesn't exist or has moved.")

    @app.errorhandler(429)
    def too_many_requests(e):
        return _error_page(429, 'Slow down a little', 'Too many attempts in a short time. Please wait a minute and try again.')

    @app.errorhandler(500)
    def server_error(e):
        return _error_page(500, 'Something went wrong', "We're on it. Please try again in a moment.")

    @app.errorhandler(400)
    def bad_request(e):
        desc = getattr(e, 'description', '') or ''
        if 'CSRF' in desc:
            return _error_page(400, 'Session expired', 'Your form session expired. Please go back, refresh the page and try again.')
        return _error_page(400, 'Bad request', 'Something was wrong with that request. Please try again.')

    # CLI commands
    from . import cli
    cli.init_app(app)

    return app
