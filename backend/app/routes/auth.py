from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from datetime import datetime

from ..extensions import db, limiter, mail
from ..models import Admin, Customer, CustomerAddress, AuditLog
from ..services.auth_service import AuthService

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        next_url = request.args.get('next') or url_for('frontend.index')

        admin = Admin.query.filter_by(email=email).first()
        if admin and admin.is_active and admin.check_password(password):
            login_user(admin, remember=True)
            db.session.add(AuditLog(
                admin_id=admin.id,
                action='login',
                resource_type='admin',
                resource_id=str(admin.id),
                ip_address=request.remote_addr
            ))
            db.session.commit()
            return redirect(next_url)

        customer = Customer.query.filter_by(email=email).first()
        if customer and customer.is_active and customer.check_password(password):
            login_user(customer, remember=True)
            return redirect(next_url)

        # Check if trying to access admin area
        if next_url and 'admin' in next_url:
            flash('Admin access requires admin privileges.', 'danger')
            return redirect(url_for('frontend.index'))

        flash('Invalid email or password.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("10 per minute", methods=["POST"])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm', '')

        errors = []
        if not name or len(name) < 2:
            errors.append('Name must be at least 2 characters.')
        if not email or '@' not in email:
            errors.append('A valid email is required.')
        if not password or len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        if password != confirm:
            errors.append('Passwords do not match.')

        if Customer.query.filter_by(email=email).first():
            errors.append('Email already registered.')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('auth/register.html')

        customer = Customer(
            name=name,
            email=email,
            phone=phone,
            is_active=True
        )
        customer.set_password(password)
        db.session.add(customer)
        db.session.commit()

        # Send welcome email (async)
        from ..tasks import dispatch, send_welcome_email
        dispatch(send_welcome_email, customer.id)

        login_user(customer, remember=True)
        flash('Account created successfully!', 'success')
        return redirect(url_for('frontend.index'))

    return render_template('auth/register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('frontend.index'))


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
@limiter.limit("5 per hour", methods=["POST"])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        if not email or '@' not in email:
            flash('A valid email is required.', 'danger')
            return render_template('auth/forgot_password.html')

        # Always return success to prevent email enumeration
        AuthService.request_password_reset(email)
        flash('If an account exists, a password reset link has been sent.', 'info')
        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html')


@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    token = request.args.get('token', '')
    if not token:
        flash('Invalid reset link.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm = request.form.get('confirm', '')

        errors = []
        if not password or len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        if password != confirm:
            errors.append('Passwords do not match.')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('auth/reset_password.html', token=token)

        try:
            AuthService.reset_password(token, password)
            flash('Password reset successful. Please log in.', 'success')
            return redirect(url_for('auth.login'))
        except ValueError as e:
            flash(str(e), 'danger')
            return render_template('auth/reset_password.html', token=token)

    return render_template('auth/reset_password.html', token=token)


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm = request.form.get('confirm', '')

        errors = []
        if not current_password:
            errors.append('Current password is required.')
        if not new_password or len(new_password) < 6:
            errors.append('New password must be at least 6 characters.')
        if new_password != confirm:
            errors.append('Passwords do not match.')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('auth/change_password.html')

        try:
            AuthService.change_password(current_user, current_password, new_password)
            flash('Password changed successfully.', 'success')
            return redirect(url_for('frontend.account'))
        except ValueError as e:
            flash(str(e), 'danger')

    return render_template('auth/change_password.html')