"""
Celery tasks package.
"""
from .email_tasks import (
    send_welcome_email,
    send_password_reset_email,
    send_order_confirmation_email,
    send_admin_order_notification
)



def dispatch(task, *args):
    """Run a background task safely.

    - USE_CELERY=true in .env  -> queued via Celery (needs Redis + a worker running)
    - otherwise                -> runs immediately in the request
    An email failure is logged and never breaks registration / checkout.
    """
    from flask import current_app
    name = getattr(task, '__name__', str(task))
    try:
        if current_app.config.get('USE_CELERY'):
            task.delay(*args)
        else:
            task(*args)
    except Exception as exc:  # noqa: BLE001
        current_app.logger.warning('Background task %s failed: %s', name, exc)


__all__ = [
    'dispatch',
    'send_welcome_email',
    'send_password_reset_email',
    'send_order_confirmation_email',
    'send_admin_order_notification',
]