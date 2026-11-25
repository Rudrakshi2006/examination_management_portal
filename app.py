import os
import secrets
from hmac import compare_digest

from flask import Flask, abort, g, redirect, render_template, request, session, url_for

import auth
import db
from admin import bp as admin_bp
from examiner import bp as examiner_bp
from student import bp as student_bp


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=None,
        DATABASE=os.path.join(app.instance_path, 'emp.sqlite3'),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        MAX_CONTENT_LENGTH=64 * 1024,
    )
    app.config.from_pyfile('config.py', silent=True)
    if test_config is not None:
        app.config.update(test_config)
    if not app.config['SECRET_KEY']:
        raise RuntimeError('Set SECRET_KEY in instance/config.py. See README.md.')
    os.makedirs(app.instance_path, exist_ok=True)
    db.init_app(app)
    app.register_blueprint(auth.bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(examiner_bp)
    app.register_blueprint(student_bp)

    def csrf_token():
        if '_csrf_token' not in session:
            session['_csrf_token'] = secrets.token_hex(32)
        return session['_csrf_token']

    app.jinja_env.globals['csrf_token'] = csrf_token

    @app.before_request
    def protect_forms():
        if request.method == 'POST':
            expected = session.get('_csrf_token', '')
            supplied = request.form.get('csrf_token', '')
            if not expected or not compare_digest(expected.encode('utf-8'), supplied.encode('utf-8')):
                abort(400, description='The form expired or is invalid. Reload the page and try again.')

    @app.get('/')
    def index():
        if g.user:
            return redirect(auth.dashboard_url(g.user))
        return redirect(url_for('auth.login'))

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(413)
    def show_error(error):
        return render_template('error.html', error=error), error.code

    return app
