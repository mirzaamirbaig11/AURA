"""
Utility functions and helpers.
"""
import uuid
import os
from datetime import datetime, timezone

def generate_order_number():
    """Generate a unique order number."""
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    random_suffix = str(uuid.uuid4())[:8]
    return f'AURA-{timestamp}-{random_suffix}'

def validate_image(file):
    """Validate uploaded image file."""
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    filename = file.filename.lower()

    if '.' not in filename:
        return False

    ext = filename.rsplit('.', 1)[1]
    if ext not in allowed_extensions:
        return False

    # Check file size (16MB max)
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)

    return size <= 16 * 1024 * 1024