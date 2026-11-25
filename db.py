import re
import sqlite3

import click
from flask import current_app, g
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db


def close_db(error=None):
    connection = g.pop('db', None)
    if connection is not None:
        connection.close()


@click.command('init-db')
@with_appcontext
def init_db_command():
    """Create missing tables and provision the first Admin; never reset data."""
    connection = get_db()
    with current_app.open_resource('schema.sql') as schema:
        connection.executescript(schema.read().decode('utf-8'))
    # Lock before checking so concurrent initialization cannot seed two Admins.
    with connection:
        connection.execute('BEGIN IMMEDIATE')
        if connection.execute("SELECT id FROM users WHERE role = 'Admin'").fetchone():
            click.echo('Database ready. Existing Admin preserved (password unchanged).')
            return
        email = str(current_app.config.get('ADMIN_EMAIL', '')).strip().lower()
        name = str(current_app.config.get('ADMIN_NAME', '')).strip()
        password = current_app.config.get('ADMIN_PASSWORD', '')
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or len(email) > 254:
            raise click.ClickException('Set a valid ADMIN_EMAIL in instance/config.py.')
        if not name or len(name) > 100 or not isinstance(password, str) or not 8 <= len(password) <= 128:
            raise click.ClickException('Set ADMIN_NAME (1–100 characters) and ADMIN_PASSWORD (8–128 characters).')
        try:
            connection.execute(
                'INSERT INTO users (name, email, password_hash, role, status) VALUES (?, ?, ?, ?, ?)',
                (name, email, generate_password_hash(password), 'Admin', 'Active'),
            )
        except sqlite3.IntegrityError as error:
            raise click.ClickException('Admin email is already registered; choose an unused ADMIN_EMAIL.') from error
    click.echo('Database ready. Admin created from local configuration.')


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
