import re
import sqlite3
from functools import wraps

from flask import Blueprint, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from db import get_db

bp = Blueprint('auth', __name__, url_prefix='/auth')


@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')
    g.user = get_db().execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone() if user_id else None


def dashboard_url(user):
    if user['role'] == 'Examiner' and user['status'] == 'Pending':
        return url_for('examiner.pending')
    endpoints = {'Admin': 'admin.dashboard', 'Student': 'student.dashboard', 'Examiner': 'examiner.dashboard'}
    return url_for(endpoints[user['role']])


def role_required(role, statuses):
    def decorate(view):
        @wraps(view)
        def guarded(*args, **kwargs):
            if g.user is None:
                return redirect(url_for('auth.login'))
            if g.user['role'] != role or g.user['status'] not in statuses:
                abort(403, description='Your account cannot access this page.')
            return view(*args, **kwargs)
        return guarded
    return decorate


@bp.route('/login', methods=('GET', 'POST'))
def login():
    errors = []
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = get_db().execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        if not user or len(password) > 128 or not check_password_hash(user['password_hash'], password):
            errors.append('Incorrect email or password.')
        elif user['status'] == 'Inactive':
            errors.append('Your account is inactive. Contact the administrator.')
        else:
            session.clear()
            session['user_id'] = user['id']
            return redirect(dashboard_url(user))
    return render_template('auth/login.html', errors=errors), 400 if errors else 200


def register(role):
    """Role comes from the route, never from submitted form fields."""
    errors = []
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        contact = request.form.get('contact', '').strip()
        department = request.form.get('department', '').strip()
        if not 1 <= len(name) <= 100:
            errors.append('Name must contain 1–100 characters.')
        if len(email) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
            errors.append('Enter a valid email address.')
        if not 8 <= len(password) <= 128:
            errors.append('Password must contain 8–128 characters.')
        if password != request.form.get('confirm_password', ''):
            errors.append('Passwords do not match.')
        if len(contact) > 30 or len(department) > 100:
            errors.append('Contact must be at most 30 characters and department at most 100.')
        if not errors:
            connection = get_db()
            try:
                with connection:
                    connection.execute(
                        'INSERT INTO users (name, email, password_hash, role, status, contact, department) '
                        'VALUES (?, ?, ?, ?, ?, ?, ?)',
                        (name, email, generate_password_hash(password), role,
                         'Pending' if role == 'Examiner' else 'Active', contact, department),
                    )
            except sqlite3.IntegrityError:
                errors.append('That email is already registered. Sign in or use another email.')
            else:
                flash('Registration complete. You can now sign in.')
                return redirect(url_for('auth.login'))
    return render_template('auth/register.html', role=role, errors=errors), 400 if errors else 200


@bp.route('/register/student', methods=('GET', 'POST'))
def register_student():
    return register('Student')


@bp.route('/register/examiner', methods=('GET', 'POST'))
def register_examiner():
    return register('Examiner')


@bp.post('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
