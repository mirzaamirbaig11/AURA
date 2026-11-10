import os
from datetime import timedelta
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
load_dotenv(os.path.join(os.path.dirname(basedir), '.env'))


def _resolve_db_url(url):
    """Make relative SQLite paths absolute (relative to the backend/ folder),
    so the app finds the same DB no matter which folder it is started from."""
    if url and url.startswith('sqlite:///') and url != 'sqlite:///:memory:':
        path = url[len('sqlite:///'):]
        if not os.path.isabs(path):
            path = os.path.join(basedir, path)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            return 'sqlite:///' + path.replace('\\', '/')
    return url



class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-string'
    SQLALCHEMY_DATABASE_URI = _resolve_db_url(os.environ.get('DATABASE_URL')) or \
        'postgresql://postgres:postgres@localhost:5432/aura_db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Session and Security
    REMEMBER_COOKIE_DURATION = timedelta(days=30)
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # Uploads
    UPLOAD_FOLDER = os.path.join(os.path.dirname(basedir), 'frontend', 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

    # Store Info
    WHATSAPP_NUMBER = os.environ.get('WHATSAPP_NUMBER', '8527756728')
    INSTAGRAM_URL = os.environ.get('INSTAGRAM_URL', 'https://instagram.com/aura_clothing')
    GOOGLE_MAPS_URL = os.environ.get('GOOGLE_MAPS_URL', 'https://maps.app.goo.gl/pRC9ZQcwyDGbPo5Q9')

    # Stripe
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
    STRIPE_CURRENCY = os.environ.get('STRIPE_CURRENCY', 'inr').lower()

    # Payment Mode
    ENABLE_ONLINE_PAYMENT = os.environ.get('ENABLE_ONLINE_PAYMENT', 'false').lower() in ['true', '1', 'yes']

    # Email
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', '1', 'yes']
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() in ['true', '1', 'yes']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@aura.com')
    MAIL_SUPPRESS_SEND = os.environ.get('MAIL_SUPPRESS_SEND', 'false').lower() in ['true', '1', 'yes']

    # Celery (off by default: emails are sent inline. Set USE_CELERY=true only with Redis + worker running)
    USE_CELERY = os.environ.get('USE_CELERY', 'false').lower() in ['true', '1', 'yes']
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL')
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND')

    # Frontend URL
    FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:5000')


class DevelopmentConfig(Config):
    DEBUG = True
    MAIL_SUPPRESS_SEND = True  # Don't send real emails in dev


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    MAIL_SUPPRESS_SEND = False


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    MAIL_SUPPRESS_SEND = True
    STRIPE_PUBLISHABLE_KEY = 'pk_test_fake'
    STRIPE_SECRET_KEY = 'sk_test_fake'
    STRIPE_WEBHOOK_SECRET = 'whsec_fake'
    ENABLE_ONLINE_PAYMENT = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}