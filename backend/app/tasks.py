"""
Celery tasks for background processing.
"""
import os
from celery import Celery
from flask import current_app


def make_celery(app):
    """Create Celery instance tied to Flask app."""
    celery = Celery(
        app.import_name,
        backend=app.config.get('CELERY_RESULT_BACKEND'),
        broker=app.config.get('CELERY_BROKER_URL')
    )
    celery.conf.update(app.config)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery


# This will be initialized in create_app
celery = None


def init_celery(app):
    """Initialize Celery with Flask app."""
    global celery
    celery = make_celery(app)
    return celery