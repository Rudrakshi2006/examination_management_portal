import re
import secrets
import sqlite3
import tempfile
import unittest
from pathlib import Path

from werkzeug.security import check_password_hash

from app import create_app
from db import get_db


class FoundationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.password = secrets.token_urlsafe(16)
        self.app = create_app({
            'TESTING': True, 'SECRET_KEY': secrets.token_hex(32),
            'DATABASE': str(Path(self.temp.name) / 'test.sqlite3'),
            'ADMIN_NAME': 'Test Admin', 'ADMIN_EMAIL': 'admin@example.test',
            'ADMIN_PASSWORD': self.password,
        })
        result = self.app.test_cli_runner().invoke(args=['init-db'])
        self.assertEqual(result.exit_code, 0, f'{result.output} {result.exception!r}')
        self.client = self.app.test_client()

    def post_form(self, path, data=None, follow_redirects=False):
        page = self.client.get(path if path != '/auth/logout' else '/', follow_redirects=True).data.decode()
        token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        return self.client.post(path, data={**(data or {}), 'csrf_token': token}, follow_redirects=follow_redirects)

    def register(self, role='student', email='student@example.test', **extra):
        return self.post_form('/auth/register/' + role, {
            'name': 'Test Person', 'email': email, 'password': self.password,
            'confirm_password': self.password, **extra,
        })

    def login(self, email='admin@example.test', password=None):
        return self.post_form('/auth/login', {'email': email, 'password': password or self.password})

    def test_init_twice_preserves_admin_password_and_other_accounts(self):
        self.register()
        self.app.config['ADMIN_PASSWORD'] = secrets.token_urlsafe(16)
        result = self.app.test_cli_runner().invoke(args=['init-db'])
        self.assertEqual(result.exit_code, 0, result.output)
        with self.app.app_context():
            users = get_db().execute('SELECT * FROM users').fetchall()
            admins = [user for user in users if user['role'] == 'Admin']
            self.assertEqual(len(admins), 1)
            self.assertEqual(len(users), 2)
            self.assertTrue(check_password_hash(admins[0]['password_hash'], self.password))

    def test_seeded_admin_login(self):
        self.assertEqual(self.login().location, '/admin/dashboard')
        self.assertIn(b'Admin dashboard', self.client.get('/admin/dashboard').data)

    def test_public_registration_cannot_create_admin_or_approve_examiner(self):
        self.assertEqual(self.client.get('/auth/register/admin').status_code, 404)
        page = self.client.get('/auth/login').data.decode()
        token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        self.assertEqual(self.client.post('/auth/register/admin', data={'csrf_token': token}).status_code, 404)
        self.assertEqual(self.register().status_code, 302)
        self.post_form('/auth/register/examiner', {
            'name': 'Examiner', 'email': 'examiner@example.test', 'password': self.password,
            'confirm_password': self.password, 'role': 'Admin', 'status': 'Approved',
        })
        # Explicit role tampering on the student route, too.
        self.post_form('/auth/register/student', {
            'name': 'Student', 'email': 'second@example.test', 'password': self.password,
            'confirm_password': self.password, 'role': 'Admin',
        })
        with self.app.app_context():
            users = get_db().execute('SELECT role, status FROM users ORDER BY id').fetchall()
            self.assertEqual([(u['role'], u['status']) for u in users],
                             [('Admin', 'Active'), ('Student', 'Active'), ('Examiner', 'Pending'), ('Student', 'Active')])

    def test_student_registration_login_dashboard(self):
        self.assertEqual(self.register().status_code, 302)
        self.assertEqual(self.login('student@example.test').location, '/student/dashboard')
        self.assertIn(b'Student dashboard', self.client.get('/student/dashboard').data)

    def test_pending_examiner_login_and_direct_url_denial(self):
        self.register('examiner', 'examiner@example.test')
        self.assertEqual(self.login('examiner@example.test').location, '/examiner/pending')
        self.assertIn(b'Approval pending', self.client.get('/examiner/pending').data)
        self.assertEqual(self.client.get('/examiner/dashboard').status_code, 403)

    def test_approved_examiner_and_status_reload(self):
        self.register('examiner', 'examiner@example.test')
        self.login('examiner@example.test')
        with self.app.app_context():
            connection = get_db()
            connection.execute("UPDATE users SET status = 'Approved' WHERE role = 'Examiner'")
            connection.commit()
        self.assertIn(b'Examiner dashboard', self.client.get('/examiner/dashboard').data)
        self.assertEqual(self.login('examiner@example.test').location, '/examiner/dashboard')
        with self.app.app_context():
            connection = get_db()
            connection.execute("UPDATE users SET status = 'Inactive' WHERE role = 'Examiner'")
            connection.commit()
        self.assertEqual(self.client.get('/examiner/dashboard').status_code, 403)
        self.assertEqual(self.client.get('/examiner/pending').status_code, 403)
        self.assertIn(b'account is inactive', self.login('examiner@example.test').data)

    def test_signed_out_dashboard_denial(self):
        for path in ('/admin/dashboard', '/student/dashboard', '/examiner/dashboard', '/examiner/pending'):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.location, '/auth/login')

    def test_wrong_role_dashboard_denial(self):
        self.register()
        self.register('examiner', 'examiner@example.test')
        for email, denied in (
            ('admin@example.test', ('/student/dashboard', '/examiner/dashboard', '/examiner/pending')),
            ('student@example.test', ('/admin/dashboard', '/examiner/dashboard', '/examiner/pending')),
            ('examiner@example.test', ('/admin/dashboard', '/student/dashboard')),
        ):
            self.login(email)
            for path in denied:
                with self.subTest(email=email, path=path):
                    self.assertEqual(self.client.get(path).status_code, 403)

    def test_duplicate_email_and_incorrect_login(self):
        self.register()
        response = self.register(email=' STUDENT@EXAMPLE.TEST ')
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'already registered', response.data)
        for email in ('admin@example.test', 'missing@example.test', "' OR 1=1 --"):
            response = self.login(email, 'incorrect-password')
            self.assertEqual(response.status_code, 400)
            self.assertIn(b'Incorrect email or password', response.data)
        self.assertEqual(self.client.get('/admin/dashboard').status_code, 302)

    def test_server_validation(self):
        for values in ({'name': ''}, {'email': 'invalid'}, {'password': 'short'},
                       {'confirm_password': 'mismatch'}, {'department': 'x' * 101}, {'contact': 'x' * 31}):
            with self.subTest(values=values):
                self.assertEqual(self.register(**values).status_code, 400)
        with self.app.app_context():
            self.assertEqual(get_db().execute('SELECT count(*) FROM users').fetchone()[0], 1)

    def test_csrf_required_on_all_mutations(self):
        for path in ('/auth/login', '/auth/register/student', '/auth/register/examiner', '/auth/logout'):
            for data in ({}, {'csrf_token': 'invalid'}, {'csrf_token': 'invalid-é'}):
                with self.subTest(path=path, data=data):
                    self.assertEqual(self.client.post(path, data=data).status_code, 400)

    def test_logout_post_only_and_clears_session(self):
        self.login()
        self.assertEqual(self.client.get('/auth/logout').status_code, 405)
        self.assertEqual(self.post_form('/auth/logout').status_code, 302)
        self.assertEqual(self.client.get('/admin/dashboard').status_code, 302)

    def test_database_constraints_and_foreign_keys(self):
        with self.app.app_context():
            connection = get_db()
            self.assertEqual(connection.execute('PRAGMA foreign_keys').fetchone()[0], 1)
            for role, status in (('Admin', 'Active'), ('Student', 'Approved'), ('Examiner', 'Active'), ('Unknown', 'Active')):
                with self.subTest(role=role, status=status), self.assertRaises(sqlite3.IntegrityError):
                    with connection:
                        connection.execute('INSERT INTO users (name, email, password_hash, role, status) VALUES (?, ?, ?, ?, ?)',
                                           ('Invalid', 'invalid@example.test', 'hash', role, status))

    def test_local_stylesheets_served(self):
        response = self.client.get('/static/vendor/bootstrap.min.css')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Bootstrap  v5.3.3', response.data[:200])
        response.close()
        response = self.client.get('/static/style.css')
        self.assertEqual(response.status_code, 200)
        response.close()


if __name__ == '__main__':
    unittest.main()
