from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_mail import Mail

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per day", "50 per hour"])
mail = Mail()

# Stripe is imported lazily in __init__.py when needed
stripe_imported = False
try:
    import stripe
    stripe_imported = True
except ImportError:
    pass


@login_manager.user_loader
def load_user(user_id):
    from .models.customer import Customer
    from .models.admin import Admin
    # user_id is a string like "admin:1" or "customer:2"
    try:
        prefix, _, raw_id = user_id.partition(':')
        uid = int(raw_id)
    except (ValueError, AttributeError):
        return None

    if prefix == 'admin':
        return db.session.get(Admin, uid)
    elif prefix == 'customer':
        return db.session.get(Customer, uid)
    return None