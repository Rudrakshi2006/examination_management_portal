import re
import secrets
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from db import get_db


class AdminChecks:
    """Run every Day 2 scenario against both fresh and Day 1-upgraded databases."""

    upgrade = False

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.password = secrets.token_urlsafe(16)
        self.app = create_app({
            'TESTING': True, 'SECRET_KEY': secrets.token_hex(32),
            'DATABASE': str(Path(temp.name) / 'admin.sqlite3'),
            'ADMIN_NAME': 'Test Admin', 'ADMIN_EMAIL': 'admin@example.test',
            'ADMIN_PASSWORD': self.password,
        })
        clock = patch('admin.now_ist', return_value='2035-01-01T09:00')
        clock.start()
        self.addCleanup(clock.stop)
        if self.upgrade:
            fixture = Path(__file__).parent / 'fixtures' / 'day1_schema.sql'
            with patch.object(self.app, 'open_resource', side_effect=lambda name: fixture.open('rb')):
                self.initialize()
        else:
            self.initialize()
        with self.app.app_context():
            connection = get_db()
            password_hash = connection.execute('SELECT password_hash FROM users').fetchone()[0]
            with connection:
                for role, status in (('Student', 'Active'), ('Examiner', 'Pending')):
                    connection.execute(
                        'INSERT INTO users (name, email, password_hash, role, status) VALUES (?, ?, ?, ?, ?)',
                        (role, role.lower() + '@example.test', password_hash, role, status),
                    )
            before = [tuple(row) for row in connection.execute('SELECT * FROM users ORDER BY id')]
        if self.upgrade:
            self.initialize()
            self.initialize()
        with self.app.app_context():
            after = [tuple(row) for row in get_db().execute('SELECT * FROM users ORDER BY id')]
        self.assertEqual(before, after, 'Schema upgrade changed existing users')
        self.client = self.app.test_client()
        self.login()

    def initialize(self):
        result = self.app.test_cli_runner().invoke(args=['init-db'])
        self.assertEqual(result.exit_code, 0, f'{result.output} {result.exception!r}')

    def post(self, path, data=None):
        page = self.client.get('/auth/login').data.decode()
        token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        return self.client.post(path, data={**(data or {}), 'csrf_token': token})

    def login(self, email='admin@example.test'):
        response = self.post('/auth/login', {'email': email, 'password': self.password})
        self.assertEqual(response.status_code, 302)

    def course(self, code='CS101'):
        response = self.post('/admin/courses/new', {'code': code, 'name': 'Database Systems', 'description': 'Course details'})
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            return get_db().execute('SELECT id FROM courses WHERE code = ?', (code,)).fetchone()[0]

    def exam_values(self, selected_course_id, **changes):
        return {
            'course_id': str(selected_course_id), 'name': 'DBMS Practical', 'exam_type': 'Practical',
            'duration_minutes': '30', 'maximum_marks': '30',
            'creation_start': '2035-01-02T09:00', 'creation_end': '2035-01-03T09:00',
            'booking_start': '2035-01-03T09:00', 'booking_end': '2035-01-04T09:00', **changes,
        }

    def exam(self, course_id):
        response = self.post('/admin/exams/new', self.exam_values(course_id))
        self.assertEqual(response.status_code, 302)
        return int(response.location.rsplit('/', 1)[1])

    def exam_row(self, exam_id):
        with self.app.app_context():
            row = get_db().execute('SELECT * FROM exams WHERE id = ?', (exam_id,)).fetchone()
            return dict(row) if row else None

    def test_dashboard_counts_and_archive_labels(self):
        page = self.client.get('/admin/dashboard').data
        for label, total in (('Courses', 0), ('Exams', 0), ('Examiners', 1), ('Students', 1), ('Slots', 0), ('Bookings', 0)):
            self.assertIn(f'<th scope="row">{label}</th><td>{total}</td>'.encode(), page)
        course_id = self.course()
        exam_id = self.exam(course_id)
        self.post(f'/admin/exams/{exam_id}/phase', {'phase': 'Closed'})
        self.post(f'/admin/exams/{exam_id}/remove')
        self.post(f'/admin/courses/{course_id}/remove')
        page = self.client.get('/admin/dashboard').data
        for label in ('Courses', 'Exams'):
            self.assertIn(f'<th scope="row">{label}</th><td>1</td>'.encode(), page)
        self.assertIn(b'including archived', page)
        self.assertIn(b'All account statuses', page)
        self.assertIn(b'Not implemented yet', page)

    def test_dashboard_counts_existing_later_tables_without_adding_features(self):
        # Synthetic counting fixtures only, not application slot/booking schemas.
        with self.app.app_context():
            connection = get_db()
            connection.executescript('CREATE TABLE slots (id INTEGER PRIMARY KEY); INSERT INTO slots VALUES (1), (2); CREATE TABLE bookings (id INTEGER PRIMARY KEY); INSERT INTO bookings VALUES (1);')
        page = self.client.get('/admin/dashboard').data
        self.assertIn(b'<th scope="row">Slots</th><td>2</td>', page)
        self.assertIn(b'<th scope="row">Bookings</th><td>1</td>', page)

    def test_course_create_edit_validation_duplicate_and_delete(self):
        course_id = self.course()
        response = self.post(f'/admin/courses/{course_id}/edit', {'code': ' cs102 ', 'name': 'Edited course', 'description': 'Updated'})
        self.assertEqual(response.status_code, 302)
        page = self.client.get('/admin/courses').data
        self.assertIn(b'CS102', page)
        self.assertIn(b'Edited course', page)
        duplicate = self.post('/admin/courses/new', {'code': 'cs102', 'name': 'Duplicate'})
        self.assertEqual(duplicate.status_code, 400)
        self.assertIn(b'already in use', duplicate.data)
        for values in ({'code': '', 'name': 'Name'}, {'code': 'C', 'name': ''}, {'code': 'C' * 31, 'name': 'Name'}, {'code': 'C', 'name': 'Name', 'description': 'x' * 2001}):
            self.assertEqual(self.post('/admin/courses/new', values).status_code, 400)
        self.assertEqual(self.post(f'/admin/courses/{course_id}/remove').status_code, 302)
        with self.app.app_context():
            self.assertEqual(get_db().execute('SELECT count(*) FROM courses').fetchone()[0], 0)

    def test_course_archival_preserves_exam_and_blocks_new_links(self):
        course_id = self.course()
        exam_id = self.exam(course_id)
        self.assertEqual(self.post(f'/admin/courses/{course_id}/remove').status_code, 302)
        self.assertIn(b'Archived', self.client.get('/admin/courses').data)
        self.assertIn(b'Course details', self.client.get('/admin/courses').data)
        self.assertEqual(self.client.get(f'/admin/exams/{exam_id}').status_code, 200)
        self.assertEqual(self.client.get(f'/admin/courses/{course_id}/edit').status_code, 403)
        self.assertEqual(self.post(f'/admin/courses/{course_id}/edit', {'code': 'Changed', 'name': 'Changed'}).status_code, 403)
        self.assertEqual(self.post(f'/admin/courses/{course_id}/remove').status_code, 403)
        self.assertEqual(self.post('/admin/exams/new', self.exam_values(course_id)).status_code, 400)
        # Existing exams retain their original archived-course link.
        self.assertEqual(self.post(f'/admin/exams/{exam_id}/edit', self.exam_values(course_id, name='Retained exam')).status_code, 302)

    def test_exam_create_edit_and_ist_display(self):
        course_id = self.course()
        exam_id = self.exam(course_id)
        page = self.client.get(f'/admin/exams/{exam_id}').data
        self.assertIn(b'Current phase: Draft', page)
        self.assertIn(b'IST (UTC+05:30)', page)
        for value in ('2035-01-02 09:00', '2035-01-03 09:00', '2035-01-04 09:00'):
            self.assertIn(value.encode(), page)
        response = self.post(f'/admin/exams/{exam_id}/edit', self.exam_values(course_id, name='Edited exam', duration_minutes='45', maximum_marks='50'))
        self.assertEqual(response.status_code, 302)
        row = self.exam_row(exam_id)
        self.assertEqual((row['name'], row['duration_minutes'], row['maximum_marks']), ('Edited exam', 45, 50))
        self.assertIn(b'Edited exam', self.client.get('/admin/exams').data)
        self.assertEqual(self.client.get(f'/admin/exams/{exam_id}/edit').status_code, 200)
        new_course_id = self.course('CS202')
        self.assertEqual(self.post(f'/admin/exams/{exam_id}/edit', self.exam_values(new_course_id)).status_code, 302)
        self.assertEqual(self.exam_row(exam_id)['course_id'], new_course_id)

    def test_invalid_timelines_and_fields_leave_exam_unchanged(self):
        course_id = self.course()
        exam_id = self.exam(course_id)
        original = self.exam_row(exam_id)
        for changes in (
            {'creation_end': '2035-01-02T09:00'},
            {'creation_end': '2035-01-04T10:00'},
            {'booking_end': '2035-01-03T09:00'},
            {'booking_start': '2035-01-01T09:00'},
            {'creation_start': ''}, {'booking_end': '2035-02-30T10:00'},
            {'booking_end': '2035-01-04T09:00+05:30'},
            {'duration_minutes': '0'}, {'maximum_marks': '1.5'},
            {'course_id': '9999'}, {'course_id': "1 OR 1=1"}, {'course_id': '9' * 100},
            {'duration_minutes': '1441'}, {'maximum_marks': '0'}, {'name': ''}, {'exam_type': ''},
        ):
            with self.subTest(changes=changes):
                values = self.exam_values(course_id, **changes)
                self.assertEqual(self.post('/admin/exams/new', values).status_code, 400)
                self.assertEqual(self.post(f'/admin/exams/{exam_id}/edit', values).status_code, 400)
                self.assertEqual(self.exam_row(exam_id), original)
        with self.app.app_context():
            self.assertEqual(get_db().execute('SELECT count(*) FROM exams').fetchone()[0], 1)

    def test_phase_controls_and_unknown_phase(self):
        course_id = self.course()
        exam_id = self.exam(course_id)
        for phase in ('Slot Creation', 'Booking Open', 'Closed', 'Completed', 'Draft'):
            self.assertEqual(self.post(f'/admin/exams/{exam_id}/phase', {'phase': phase}).status_code, 302)
            self.assertEqual(self.exam_row(exam_id)['phase'], phase)
        self.assertEqual(self.post(f'/admin/exams/{exam_id}/phase', {'phase': 'Published'}).status_code, 400)
        self.assertEqual(self.exam_row(exam_id)['phase'], 'Draft')

    def test_booking_start_boundary_cannot_reopen_creation(self):
        course_id = self.course()
        exam_id = self.exam(course_id)
        with patch('admin.now_ist', return_value='2035-01-03T09:00'):
            for phase in ('Draft', 'Slot Creation'):
                self.assertEqual(self.post(f'/admin/exams/{exam_id}/phase', {'phase': phase}).status_code, 400)
            self.assertEqual(self.post(f'/admin/exams/{exam_id}/phase', {'phase': 'Booking Open'}).status_code, 302)
            self.assertEqual(self.post(f'/admin/exams/{exam_id}/edit', self.exam_values(course_id, booking_start='2035-01-03T10:00')).status_code, 400)
            self.assertEqual(self.post(f'/admin/exams/{exam_id}/edit', self.exam_values(course_id, creation_end='2035-01-03T09:01', booking_start='2035-01-03T09:01')).status_code, 400)
            self.assertEqual(self.post(f'/admin/exams/{exam_id}/edit', self.exam_values(course_id, name='Safe metadata edit')).status_code, 302)

    def test_unused_draft_deletion_and_non_draft_archive(self):
        course_id = self.course()
        draft_id = self.exam(course_id)
        self.assertEqual(self.post(f'/admin/exams/{draft_id}/remove').status_code, 302)
        self.assertIsNone(self.exam_row(draft_id))
        exam_id = self.exam(course_id)
        self.post(f'/admin/exams/{exam_id}/phase', {'phase': 'Completed'})
        self.assertEqual(self.post(f'/admin/exams/{exam_id}/remove').status_code, 302)
        self.assertEqual(self.exam_row(exam_id)['archived'], 1)
        self.assertIn(b'Archived (read-only)', self.client.get(f'/admin/exams/{exam_id}').data)
        self.assertIn(b'DBMS Practical', self.client.get('/admin/exams').data)
        for path in (f'/admin/exams/{exam_id}/edit', f'/admin/exams/{exam_id}/phase', f'/admin/exams/{exam_id}/remove'):
            self.assertEqual(self.post(path, self.exam_values(course_id, phase='Draft')).status_code, 403)

    def test_referenced_draft_is_archived_and_reference_survives(self):
        exam_id = self.exam(self.course())
        with self.app.app_context():
            connection = get_db()
            # A synthetic dependent table tests the FK fallback without implementing later features.
            connection.execute('CREATE TABLE retained_history (exam_id INTEGER REFERENCES exams(id) ON DELETE RESTRICT)')
            connection.execute('INSERT INTO retained_history VALUES (?)', (exam_id,))
            connection.commit()
        self.assertEqual(self.post(f'/admin/exams/{exam_id}/remove').status_code, 302)
        self.assertEqual(self.exam_row(exam_id)['archived'], 1)
        with self.app.app_context():
            self.assertEqual(get_db().execute('SELECT exam_id FROM retained_history').fetchone()[0], exam_id)

    def admin_routes(self, course_id, exam_id):
        return (
            ('GET', '/admin/dashboard'), ('GET', '/admin/courses'), ('GET', '/admin/exams'),
            ('GET', '/admin/courses/new'), ('POST', '/admin/courses/new'),
            ('GET', f'/admin/courses/{course_id}/edit'), ('POST', f'/admin/courses/{course_id}/edit'),
            ('POST', f'/admin/courses/{course_id}/remove'),
            ('GET', '/admin/exams/new'), ('POST', '/admin/exams/new'),
            ('GET', f'/admin/exams/{exam_id}'), ('GET', f'/admin/exams/{exam_id}/edit'),
            ('POST', f'/admin/exams/{exam_id}/edit'), ('POST', f'/admin/exams/{exam_id}/phase'),
            ('POST', f'/admin/exams/{exam_id}/remove'),
        )

    def test_non_admin_access_denied_on_all_admin_routes(self):
        course_id = self.course()
        exam_id = self.exam(course_id)
        routes = self.admin_routes(course_id, exam_id)
        for email in ('student@example.test', 'examiner@example.test'):
            self.login(email)
            for method, path in routes:
                with self.subTest(email=email, method=method, path=path):
                    response = self.post(path) if method == 'POST' else self.client.get(path)
                    self.assertEqual(response.status_code, 403)
        with self.app.app_context():
            connection = get_db()
            connection.execute("UPDATE users SET status = 'Approved' WHERE role = 'Examiner'")
            connection.commit()
        for method, path in routes:
            response = self.post(path) if method == 'POST' else self.client.get(path)
            self.assertEqual(response.status_code, 403)
        self.post('/auth/logout')
        for method, path in routes:
            response = self.post(path) if method == 'POST' else self.client.get(path)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.location, '/auth/login')
        self.assertEqual(self.exam_row(exam_id)['archived'], 0)

    def test_inactive_admin_denied_without_relogin(self):
        course_id = self.course()
        exam_id = self.exam(course_id)
        with self.app.app_context():
            connection = get_db()
            connection.execute("UPDATE users SET status = 'Inactive' WHERE role = 'Admin'")
            connection.commit()
        for method, path in self.admin_routes(course_id, exam_id):
            response = self.post(path) if method == 'POST' else self.client.get(path)
            self.assertEqual(response.status_code, 403)

    def test_csrf_post_only_mutations_and_missing_ids(self):
        course_id = self.course()
        exam_id = self.exam(course_id)
        for method, path in self.admin_routes(course_id, exam_id):
            if method == 'POST':
                self.assertEqual(self.client.post(path).status_code, 400)
                self.assertEqual(self.client.post(path, data={'csrf_token': 'wrong'}).status_code, 400)
                if path.endswith(('/remove', '/phase')):
                    self.assertEqual(self.client.get(path).status_code, 405)
        for path in ('/admin/courses/9999/edit', '/admin/exams/9999', '/admin/exams/9999/edit'):
            self.assertEqual(self.client.get(path).status_code, 404)
        for path in ('/admin/courses/9999/remove', '/admin/exams/9999/remove', '/admin/exams/9999/phase'):
            self.assertEqual(self.post(path).status_code, 404)

    def test_reinitialization_preserves_users_courses_and_exams(self):
        course_id = self.course()
        exam_id = self.exam(course_id)
        before = self.exam_row(exam_id)
        self.app.config['ADMIN_PASSWORD'] = secrets.token_urlsafe(16)
        self.initialize()
        self.initialize()
        self.assertEqual(self.exam_row(exam_id), before)
        self.login()
        self.login('student@example.test')
        self.assertEqual(self.client.get('/student/dashboard').status_code, 200)
        self.login('examiner@example.test')
        self.assertEqual(self.client.get('/examiner/pending').status_code, 200)

    def test_sql_constraints_enforce_references_order_and_phase(self):
        course_id = self.course()
        exam_id = self.exam(course_id)
        with self.app.app_context():
            connection = get_db()
            for sql in (
                "UPDATE exams SET course_id = 9999 WHERE id = ?",
                "UPDATE exams SET phase = 'Invalid' WHERE id = ?",
                'UPDATE exams SET booking_end = booking_start WHERE id = ?',
                'DELETE FROM courses WHERE id = ?',
            ):
                with self.subTest(sql=sql), self.assertRaises(sqlite3.IntegrityError):
                    with connection:
                        connection.execute(sql, (course_id if sql.startswith('DELETE') else exam_id,))


class FreshAdminTests(AdminChecks, unittest.TestCase):
    pass


class UpgradedDay1AdminTests(AdminChecks, unittest.TestCase):
    upgrade = True


if __name__ == '__main__':
    unittest.main()
