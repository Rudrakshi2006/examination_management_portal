import secrets
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from werkzeug.security import check_password_hash

from app import create_app
from db import get_db
from test_admin import AdminChecks


class Day3Checks:
    upgrade = False
    initialize = AdminChecks.initialize
    post = AdminChecks.post
    login = AdminChecks.login
    course = AdminChecks.course
    exam = AdminChecks.exam
    exam_values = AdminChecks.exam_values
    exam_row = AdminChecks.exam_row

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.password = secrets.token_urlsafe(16)
        self.app = create_app({
            'TESTING': True, 'SECRET_KEY': secrets.token_hex(32),
            'DATABASE': str(Path(temp.name) / 'day3.sqlite3'),
            'ADMIN_NAME': 'Test Admin', 'ADMIN_EMAIL': 'admin@example.test',
            'ADMIN_PASSWORD': self.password,
        })
        clock = patch('admin.now_ist', return_value='2035-01-01T09:00')
        clock.start()
        self.addCleanup(clock.stop)
        if self.upgrade:
            fixture = Path(__file__).parent / 'fixtures' / 'day2_schema.sql'
            with patch.object(self.app, 'open_resource', side_effect=lambda name: fixture.open('rb')):
                self.initialize()
        else:
            self.initialize()
        self.client = self.app.test_client()
        self.student_id = self.register('student', 'Student Alice', 'alice@example.test')
        self.pending_id = self.register('examiner', 'Examiner Priya', 'priya@example.test')
        self.login()
        self.course_id = self.course()
        self.exam_id = self.exam(self.course_id)
        with self.app.app_context():
            before = {table: [tuple(row) for row in get_db().execute(f'SELECT * FROM {table} ORDER BY id')]
                      for table in ('users', 'courses', 'exams')}
        if self.upgrade:
            self.initialize()
            self.initialize()
        with self.app.app_context():
            after = {table: [tuple(row) for row in get_db().execute(f'SELECT * FROM {table} ORDER BY id')]
                     for table in ('users', 'courses', 'exams')}
        self.assertEqual(before, after)

    def account_values(self, name='Direct Examiner', email='direct@example.test', **changes):
        return {'name': name, 'email': email, 'password': self.password,
                'confirm_password': self.password, **changes}

    def register(self, role, name, email):
        response = self.post('/auth/register/' + role, self.account_values(name, email))
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            return get_db().execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()[0]

    def approved(self, email='direct@example.test'):
        response = self.post('/admin/people/examiners/new', self.account_values(email=email))
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            return get_db().execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()[0]

    def assign(self, examiner_id, exam_id=None):
        return self.post(f'/admin/exams/{exam_id or self.exam_id}/assign', {'examiner_id': str(examiner_id)})

    def criterion(self, name, maximum, exam_id=None):
        exam_id = exam_id or self.exam_id
        response = self.post(f'/admin/exams/{exam_id}/rubrics/new', {'name': name, 'maximum_marks': str(maximum), 'description': 'Demo criterion'})
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            return get_db().execute('SELECT id FROM rubrics WHERE exam_id = ? AND name = ?', (exam_id, name)).fetchone()[0]

    def detail(self):
        response = self.client.get(f'/admin/exams/{self.exam_id}')
        self.assertEqual(response.status_code, 200)
        return response.data

    def test_pending_approval_assignment_dashboard_and_live_deactivation(self):
        admin_client = self.client
        self.client = self.app.test_client()
        self.login('priya@example.test')
        self.assertEqual(self.client.get('/examiner/pending').status_code, 200)
        self.assertEqual(self.client.get('/examiner/dashboard').status_code, 403)
        examiner_client = self.client
        self.client = admin_client
        self.assertEqual(self.post(f'/admin/people/{self.pending_id}/approve').status_code, 302)
        self.assertEqual(self.assign(self.pending_id).status_code, 302)
        self.assertIn(b'Examiner Priya', self.detail())
        self.assertIn(b'DBMS Practical', examiner_client.get('/examiner/dashboard').data)
        self.assertEqual(self.post(f'/admin/people/{self.pending_id}/deactivate').status_code, 302)
        self.assertEqual(examiner_client.get('/examiner/dashboard').status_code, 403)
        self.assertEqual(examiner_client.get('/examiner/pending').status_code, 403)
        self.assertIn(b'Inactive', self.detail())
        with self.app.app_context():
            self.assertEqual(get_db().execute('SELECT count(*) FROM examiner_assignments').fetchone()[0], 1)

    def test_admin_create_examiner_hashing_and_fixed_role_status(self):
        response = self.post('/admin/people/examiners/new', self.account_values(email=' DIRECT@EXAMPLE.TEST ', role='Admin', status='Active'))
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            user = get_db().execute("SELECT * FROM users WHERE email = 'direct@example.test'").fetchone()
            self.assertEqual((user['role'], user['status']), ('Examiner', 'Approved'))
            self.assertNotEqual(user['password_hash'], self.password)
            self.assertTrue(check_password_hash(user['password_hash'], self.password))
        self.login('direct@example.test')
        self.assertIn(b'No exams assigned yet', self.client.get('/examiner/dashboard').data)

    def test_account_validation_and_duplicate_email(self):
        self.approved()
        self.assertIn(b'already registered', self.post('/admin/people/examiners/new', self.account_values()).data)
        for changes in ({'name': ''}, {'name': 'x' * 101}, {'email': 'bad'}, {'password': 'short'},
                        {'confirm_password': 'different'}, {'contact': 'x' * 31}, {'department': 'x' * 101}):
            with self.subTest(changes=changes):
                self.assertEqual(self.post('/admin/people/examiners/new', self.account_values(**changes)).status_code, 400)
        with self.app.app_context():
            self.assertEqual(get_db().execute('SELECT count(*) FROM users').fetchone()[0], 4)

    def test_status_actions_only_for_examiners_and_valid_transitions(self):
        for user_id in (1, self.student_id, 99999, '9' * 100):
            for action in ('approve', 'deactivate'):
                self.assertEqual(self.post(f'/admin/people/{user_id}/{action}').status_code, 404)
        self.assertEqual(self.post(f'/admin/people/{self.pending_id}/approve').status_code, 302)
        self.assertEqual(self.post(f'/admin/people/{self.pending_id}/approve').status_code, 400)
        self.assertEqual(self.post(f'/admin/people/{self.pending_id}/deactivate').status_code, 302)
        self.assertEqual(self.post(f'/admin/people/{self.pending_id}/deactivate').status_code, 400)
        self.assertEqual(self.post(f'/admin/people/{self.pending_id}/approve').status_code, 400)

    def test_assignment_eligibility_duplicates_and_invalid_ids(self):
        approved_id = self.approved()
        for user_id in (self.pending_id, self.student_id, 1, 9999, 'abc', '', '9' * 100, '1 OR 1=1'):
            self.assertEqual(self.assign(user_id).status_code, 400)
        self.assertEqual(self.assign(approved_id).status_code, 302)
        self.assertIn(b'already assigned', self.assign(approved_id).data)
        self.post(f'/admin/people/{approved_id}/deactivate')
        another_exam = self.exam(self.course_id)
        self.assertEqual(self.assign(approved_id, another_exam).status_code, 400)
        with self.app.app_context():
            self.assertEqual(get_db().execute('SELECT count(*) FROM examiner_assignments').fetchone()[0], 1)

    def test_dashboard_is_scoped_to_logged_in_examiner_and_retains_history(self):
        first = self.approved()
        second = self.approved('other@example.test')
        self.assign(first)
        other_exam = self.exam(self.course_id)
        self.post(f'/admin/exams/{other_exam}/edit', self.exam_values(self.course_id, name='Private Other Exam'))
        self.assign(second, other_exam)
        self.post(f'/admin/exams/{self.exam_id}/remove')  # Assignment forces archival, even in Draft.
        self.login('direct@example.test')
        page = self.client.get(f'/examiner/dashboard?examiner_id={second}').data
        self.assertIn(b'DBMS Practical', page)
        self.assertIn(b'Archived', page)
        self.assertNotIn(b'Private Other Exam', page)
        self.login('other@example.test')
        page = self.client.get('/examiner/dashboard').data
        self.assertIn(b'Private Other Exam', page)
        self.assertNotIn(b'DBMS Practical', page)

    def test_people_search_name_id_and_role_scope(self):
        page = self.client.get('/admin/people').data
        self.assertIn(b'Student Alice', page)
        self.assertIn(b'Examiner Priya', page)
        self.assertNotIn(b'Test Admin', page)
        page = self.client.get('/admin/people', query_string={'q': 'pRiYa'}).data
        self.assertIn(b'Examiner Priya', page)
        self.assertNotIn(b'Student Alice', page)
        page = self.client.get('/admin/people', query_string={'q': str(self.student_id)}).data
        self.assertIn(b'Student Alice', page)
        self.assertNotIn(b'Examiner Priya', page)
        for query in ('1', "' OR 1=1 --", '%', '9' * 100):
            self.assertIn(b'No matching people', self.client.get('/admin/people', query_string={'q': query}).data)

    def test_exam_search_name_id_and_archived_records(self):
        other = self.exam(self.course_id)
        self.post(f'/admin/exams/{other}/edit', self.exam_values(self.course_id, name='Networks Oral'))
        self.post(f'/admin/exams/{self.exam_id}/phase', {'phase': 'Closed'})
        self.post(f'/admin/exams/{self.exam_id}/remove')
        for query in ('dbms', str(self.exam_id)):
            page = self.client.get('/admin/exams', query_string={'q': query}).data
            self.assertIn(b'DBMS Practical', page)
            self.assertIn(b'Archived', page)
            self.assertNotIn(b'Networks Oral', page)
        for query in ('missing', "' OR 1=1 --", '%', '9' * 100):
            self.assertIn(b'No matching exams', self.client.get('/admin/exams', query_string={'q': query}).data)

    def test_rubric_30_mark_total_weights_edit_and_delete(self):
        first = self.criterion('Query Correctness', 15)
        self.assertIn(b'Rubric total: 15 / 30', self.detail())
        self.assertIn(b'Incomplete', self.detail())
        self.assertIn(b'50.00%', self.detail())
        second = self.criterion('Execution', 10)
        self.assertIn(b'Rubric total: 25 / 30', self.detail())
        self.criterion('Explanation', 5)
        page = self.detail()
        for text in (b'Rubric total: 30 / 30', b'Matches exam maximum', b'50.00%', b'33.33%', b'16.67%'):
            self.assertIn(text, page)
        path = f'/admin/exams/{self.exam_id}/rubrics/{first}/edit'
        self.assertEqual(self.client.get(path).status_code, 200)
        self.assertEqual(self.post(path, {'name': 'Query accuracy', 'maximum_marks': '14', 'description': 'Edited description'}).status_code, 302)
        self.assertIn(b'Rubric total: 29 / 30', self.detail())
        self.assertIn(b'Edited description', self.detail())
        self.assertEqual(self.post(f'/admin/exams/{self.exam_id}/rubrics/{second}/delete').status_code, 302)
        self.assertIn(b'Rubric total: 19 / 30', self.detail())
        self.assertNotIn(b'>Execution<', self.detail())

    def test_rubric_validation_overflow_duplicates_and_exam_maximum(self):
        criterion_id = self.criterion('Query', 15)
        path = f'/admin/exams/{self.exam_id}/rubrics/new'
        for values in ({'name': '', 'maximum_marks': '1'}, {'name': 'Other', 'maximum_marks': '31'},
                       {'name': 'Other', 'maximum_marks': '16'}, {'name': 'Other', 'maximum_marks': '0'},
                       {'name': 'Other', 'maximum_marks': '-1'}, {'name': 'Other', 'maximum_marks': '1.5'},
                       {'name': 'Other', 'maximum_marks': '9' * 100}, {'name': 'Other', 'maximum_marks': ''},
                       {'name': 'Other', 'maximum_marks': '1', 'description': 'x' * 2001},
                       {'name': 'qUeRy', 'maximum_marks': '1'}):
            self.assertEqual(self.post(path, values).status_code, 400)
        self.criterion('Remaining', 15)
        edit = f'/admin/exams/{self.exam_id}/rubrics/{criterion_id}/edit'
        self.assertEqual(self.post(edit, {'name': 'Query', 'maximum_marks': '16'}).status_code, 400)
        self.assertEqual(self.post(f'/admin/exams/{self.exam_id}/edit', self.exam_values(self.course_id, maximum_marks='29')).status_code, 400)
        self.assertEqual(self.exam_row(self.exam_id)['maximum_marks'], 30)
        self.assertEqual(self.post(f'/admin/exams/{self.exam_id}/edit', self.exam_values(self.course_id, maximum_marks='40')).status_code, 302)
        self.assertIn(b'Rubric total: 30 / 40', self.detail())
        self.assertIn(b'37.50%', self.detail())

    def test_criterion_ids_are_scoped_and_archived_exam_is_read_only(self):
        criterion_id = self.criterion('Query', 15)
        other_exam = self.exam(self.course_id)
        for suffix in ('edit', 'delete'):
            self.assertEqual(self.post(f'/admin/exams/{other_exam}/rubrics/{criterion_id}/{suffix}', {'name': 'Stolen', 'maximum_marks': '1'}).status_code, 404)
        self.post(f'/admin/exams/{self.exam_id}/remove')
        self.assertEqual(self.exam_row(self.exam_id)['archived'], 1)
        self.assertIn(b'Query', self.detail())
        approved_id = self.approved()
        self.assertEqual(self.assign(approved_id).status_code, 403)
        for suffix in ('new', f'{criterion_id}/edit', f'{criterion_id}/delete'):
            path = f'/admin/exams/{self.exam_id}/rubrics/{suffix}'
            self.assertEqual(self.post(path, {'name': 'Changed', 'maximum_marks': '1'}).status_code, 403)

    def routes(self, criterion_id):
        exam = f'/admin/exams/{self.exam_id}'
        return (('GET', '/admin/people'), ('GET', '/admin/people/examiners/new'),
                ('POST', '/admin/people/examiners/new'), ('POST', f'/admin/people/{self.pending_id}/approve'),
                ('POST', f'/admin/people/{self.pending_id}/deactivate'), ('POST', exam + '/assign'),
                ('GET', exam + '/rubrics/new'), ('POST', exam + '/rubrics/new'),
                ('GET', exam + f'/rubrics/{criterion_id}/edit'), ('POST', exam + f'/rubrics/{criterion_id}/edit'),
                ('POST', exam + f'/rubrics/{criterion_id}/delete'))

    def test_all_new_routes_enforce_roles_and_status(self):
        criterion_id = self.criterion('Query', 15)
        self.approved()
        for email in ('alice@example.test', 'priya@example.test', 'direct@example.test'):
            self.login(email)
            for method, path in self.routes(criterion_id):
                response = self.post(path) if method == 'POST' else self.client.get(path)
                self.assertEqual(response.status_code, 403, path)
        self.login()
        with self.app.app_context():
            connection = get_db()
            connection.execute("UPDATE users SET status = 'Inactive' WHERE role = 'Admin'")
            connection.commit()
        for method, path in self.routes(criterion_id):
            response = self.post(path) if method == 'POST' else self.client.get(path)
            self.assertEqual(response.status_code, 403, path)
        self.post('/auth/logout')
        for method, path in self.routes(criterion_id):
            response = self.post(path) if method == 'POST' else self.client.get(path)
            self.assertEqual(response.status_code, 302, path)
            self.assertEqual(response.location, '/auth/login')

    def test_csrf_post_only_and_missing_records(self):
        criterion_id = self.criterion('Query', 15)
        for method, path in self.routes(criterion_id):
            if method == 'POST':
                self.assertEqual(self.client.post(path).status_code, 400)
                self.assertEqual(self.client.post(path, data={'csrf_token': 'wrong'}).status_code, 400)
                if not path.endswith(('/new', '/edit')):
                    self.assertEqual(self.client.get(path).status_code, 405)
        self.assertEqual(self.assign(9999, 9999).status_code, 404)
        self.assertEqual(self.client.get(f'/admin/exams/{self.exam_id}/rubrics/9999/edit').status_code, 404)
        huge_id = '9' * 100
        self.assertEqual(self.client.get(f'/admin/exams/{huge_id}').status_code, 404)
        self.assertEqual(self.client.get(f'/admin/exams/{self.exam_id}/rubrics/{huge_id}/edit').status_code, 404)

    def test_repeat_init_preserves_new_data_and_schema_constraints(self):
        examiner_id = self.approved()
        self.assign(examiner_id)
        self.criterion('Query', 15)
        self.initialize()
        self.initialize()
        self.assertIn(b'Direct Examiner', self.detail())
        self.assertIn(b'Rubric total: 15 / 30', self.detail())
        with self.app.app_context():
            connection = get_db()
            for sql, params in (
                ('INSERT INTO examiner_assignments VALUES (?, ?)', (self.exam_id, examiner_id)),
                ('INSERT INTO examiner_assignments VALUES (?, ?)', (99999, examiner_id)),
                ('INSERT INTO rubrics (exam_id, name, maximum_marks) VALUES (?, ?, ?)', (self.exam_id, 'query', 1)),
            ):
                with self.assertRaises(sqlite3.IntegrityError):
                    with connection:
                        connection.execute(sql, params)


class FreshDay3Tests(Day3Checks, unittest.TestCase):
    pass


class UpgradedDay2Tests(Day3Checks, unittest.TestCase):
    upgrade = True


if __name__ == '__main__':
    unittest.main()
