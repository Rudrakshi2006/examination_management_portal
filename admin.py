import re
import sqlite3
from datetime import datetime, timedelta, timezone

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from auth import insert_account, role_required, validate_account
from db import get_db

bp = Blueprint('admin', __name__, url_prefix='/admin')
PHASES = ('Draft', 'Slot Creation', 'Booking Open', 'Closed', 'Completed')
TIMELINE_FIELDS = ('creation_start', 'creation_end', 'booking_start', 'booking_end')
IST = timezone(timedelta(hours=5, minutes=30))


def now_ist():
    return datetime.now(IST).replace(tzinfo=None).isoformat(timespec='minutes')


def get_course(course_id):
    if not 0 < course_id <= 9223372036854775807:
        abort(404, description='Course not found.')
    course = get_db().execute('SELECT * FROM courses WHERE id = ?', (course_id,)).fetchone()
    if course is None:
        abort(404, description='Course not found.')
    return course


def get_exam(exam_id):
    if not 0 < exam_id <= 9223372036854775807:
        abort(404, description='Exam not found.')
    exam = get_db().execute(
        'SELECT exams.*, courses.code AS course_code, courses.name AS course_name '
        'FROM exams JOIN courses ON courses.id = exams.course_id WHERE exams.id = ?', (exam_id,),
    ).fetchone()
    if exam is None:
        abort(404, description='Exam not found.')
    return exam


@bp.get('/dashboard')
@role_required('Admin', ('Active',))
def dashboard():
    connection = get_db()
    counts = {
        'Courses': connection.execute('SELECT count(*) FROM courses').fetchone()[0],
        'Exams': connection.execute('SELECT count(*) FROM exams').fetchone()[0],
        'Examiners': connection.execute("SELECT count(*) FROM users WHERE role = 'Examiner'").fetchone()[0],
        'Students': connection.execute("SELECT count(*) FROM users WHERE role = 'Student'").fetchone()[0],
    }
    unavailable = []
    # These tables belong to later milestones; do not create partial schemas.
    for table, label in (('slots', 'Slots'), ('bookings', 'Bookings')):
        exists = connection.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone()
        # table is an internal constant from the pair above, never request input.
        counts[label] = connection.execute(f'SELECT count(*) FROM {table}').fetchone()[0] if exists else 0
        if not exists:
            unavailable.append(label)
    return render_template('admin/dashboard.html', counts=counts, unavailable=unavailable)


@bp.get('/courses')
@role_required('Admin', ('Active',))
def courses():
    rows = get_db().execute('SELECT * FROM courses ORDER BY archived, code').fetchall()
    return render_template('admin/courses.html', courses=rows)


@bp.route('/courses/new', methods=('GET', 'POST'))
@bp.route('/courses/<int:course_id>/edit', methods=('GET', 'POST'))
@role_required('Admin', ('Active',))
def course_form(course_id=None):
    course = get_course(course_id) if course_id is not None else None
    if course is not None and course['archived']:
        abort(403, description='Archived courses are read-only.')
    errors = []
    values = dict(request.form) if request.method == 'POST' else dict(course or {})
    if request.method == 'POST':
        code = values.get('code', '').strip().upper()
        name = values.get('name', '').strip()
        description = values.get('description', '').strip()
        if not 1 <= len(code) <= 30 or not 1 <= len(name) <= 100:
            errors.append('Course code must contain 1–30 characters and name 1–100 characters.')
        if len(description) > 2000:
            errors.append('Description must be at most 2000 characters.')
        if not errors:
            connection = get_db()
            try:
                with connection:
                    if course is None:
                        connection.execute('INSERT INTO courses (code, name, description) VALUES (?, ?, ?)', (code, name, description))
                    else:
                        connection.execute('UPDATE courses SET code = ?, name = ?, description = ? WHERE id = ?', (code, name, description, course_id))
            except sqlite3.IntegrityError:
                errors.append('That course code is already in use, including archived courses.')
            else:
                flash('Course saved.')
                return redirect(url_for('admin.courses'))
    return render_template('admin/course_form.html', values=values, course=course, errors=errors), 400 if errors else 200


@bp.post('/courses/<int:course_id>/remove')
@role_required('Admin', ('Active',))
def remove_course(course_id):
    course = get_course(course_id)
    if course['archived']:
        abort(403, description='This course is already archived.')
    connection = get_db()
    try:
        with connection:
            connection.execute('DELETE FROM courses WHERE id = ?', (course_id,))
    except sqlite3.IntegrityError:
        with connection:
            connection.execute('UPDATE courses SET archived = 1 WHERE id = ?', (course_id,))
        flash('Course archived because it is referenced. Its exams remain accessible.')
    else:
        flash('Unused course deleted.')
    return redirect(url_for('admin.courses'))


@bp.get('/exams')
@role_required('Admin', ('Active',))
def exams():
    query = request.args.get('q', '').strip()
    rows = get_db().execute(
        'SELECT exams.*, courses.code AS course_code FROM exams '
        'JOIN courses ON courses.id = exams.course_id '
        'WHERE (? = ? OR instr(lower(exams.name), lower(?)) > 0 OR exams.id = ?) '
        'ORDER BY exams.archived, exams.id DESC', (query, '', query, numeric_search_id(query)),
    ).fetchall()
    return render_template('admin/exams.html', exams=rows, query=query)


def validate_exam(values, existing):
    errors = []
    data = {field: values.get(field, '').strip() for field in ('name', 'exam_type') + TIMELINE_FIELDS}
    if not 1 <= len(data['name']) <= 100 or not 1 <= len(data['exam_type']) <= 50:
        errors.append('Exam name must contain 1–100 characters and type 1–50 characters.')
    for field, label, maximum in (('course_id', 'Course', 2147483647), ('duration_minutes', 'Duration', 1440), ('maximum_marks', 'Maximum marks', 10000)):
        try:
            value = int(values.get(field, ''))
            if not 1 <= value <= maximum:
                raise ValueError
            data[field] = value
        except (ValueError, TypeError):
            errors.append(f'{label} must be a whole number between 1 and {maximum}.')
    if 'course_id' in data:
        course = get_db().execute('SELECT * FROM courses WHERE id = ?', (data['course_id'],)).fetchone()
        if course is None or (course['archived'] and (existing is None or existing['course_id'] != course['id'])):
            errors.append('Choose an existing, unarchived course.')
    for field in TIMELINE_FIELDS:
        try:
            data[field] = datetime.strptime(data[field], '%Y-%m-%dT%H:%M').isoformat(timespec='minutes')
        except ValueError:
            errors.append('Enter all four timeline dates as valid local IST dates and times.')
            break
    if not errors:
        if existing:
            total = get_db().execute('SELECT coalesce(sum(maximum_marks), 0) FROM rubrics WHERE exam_id = ?', (existing['id'],)).fetchone()[0]
            if data['maximum_marks'] < total:
                errors.append(f'Exam maximum cannot be lower than the rubric total ({total}).')
        if not data['creation_start'] < data['creation_end'] <= data['booking_start'] < data['booking_end']:
            errors.append('Timeline must satisfy: creation start < creation end ≤ booking start < booking end.')
        if existing and now_ist() >= existing['booking_start']:
            if data['booking_start'] > existing['booking_start'] or data['creation_end'] > existing['creation_end']:
                errors.append('Once booking has begun, do not move booking start or creation end later and reopen examiner editing.')
    return data, errors


@bp.route('/exams/new', methods=('GET', 'POST'))
@bp.route('/exams/<int:exam_id>/edit', methods=('GET', 'POST'))
@role_required('Admin', ('Active',))
def exam_form(exam_id=None):
    exam = get_exam(exam_id) if exam_id is not None else None
    if exam is not None and exam['archived']:
        abort(403, description='Archived exams are read-only.')
    values = dict(request.form) if request.method == 'POST' else dict(exam or {})
    errors = []
    if request.method == 'POST':
        connection = get_db()
        with connection:
            connection.execute('BEGIN IMMEDIATE')
            if exam is not None:
                exam = get_active_exam(exam_id)
            data, errors = validate_exam(values, exam)
            if not errors:
                fields = ('course_id', 'name', 'exam_type', 'duration_minutes', 'maximum_marks') + TIMELINE_FIELDS
                parameters = tuple(data[field] for field in fields)
                if exam is None:
                    cursor = connection.execute(
                        'INSERT INTO exams (course_id, name, exam_type, duration_minutes, maximum_marks, creation_start, creation_end, booking_start, booking_end) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', parameters,
                    )
                    exam_id = cursor.lastrowid
                else:
                    connection.execute(
                        'UPDATE exams SET course_id = ?, name = ?, exam_type = ?, duration_minutes = ?, maximum_marks = ?, creation_start = ?, creation_end = ?, booking_start = ?, booking_end = ? WHERE id = ?', parameters + (exam_id,),
                    )
        if not errors:
            flash('Exam saved. All timeline times are IST.')
            return redirect(url_for('admin.exam_detail', exam_id=exam_id))
    available_courses = get_db().execute('SELECT * FROM courses ORDER BY archived, code').fetchall()
    return render_template('admin/exam_form.html', values=values, exam=exam, courses=available_courses, errors=errors), 400 if errors else 200


@bp.get('/exams/<int:exam_id>')
@role_required('Admin', ('Active',))
def exam_detail(exam_id):
    return render_exam_detail(exam_id)


@bp.post('/exams/<int:exam_id>/phase')
@role_required('Admin', ('Active',))
def change_phase(exam_id):
    exam = get_exam(exam_id)
    phase = request.form.get('phase', '')
    errors = []
    if exam['archived']:
        abort(403, description='Archived exams are read-only.')
    if phase not in PHASES:
        errors.append('Choose a valid exam phase.')
    elif phase in ('Draft', 'Slot Creation') and now_ist() >= exam['booking_start']:
        errors.append('Cannot reopen examiner editing after booking has begun.')
    if errors:
        return render_exam_detail(exam_id, errors, 400)
    with get_db() as connection:
        connection.execute('UPDATE exams SET phase = ? WHERE id = ?', (phase, exam_id))
    flash('Exam phase updated.')
    return redirect(url_for('admin.exam_detail', exam_id=exam_id))


@bp.post('/exams/<int:exam_id>/remove')
@role_required('Admin', ('Active',))
def remove_exam(exam_id):
    exam = get_exam(exam_id)
    if exam['archived']:
        abort(403, description='This exam is already archived.')
    connection = get_db()
    # Retain non-Draft history even before downstream records exist.
    if exam['phase'] != 'Draft':
        with connection:
            connection.execute('UPDATE exams SET archived = 1 WHERE id = ?', (exam_id,))
        flash('Exam archived; its history remains accessible.')
    else:
        try:
            with connection:
                connection.execute('DELETE FROM exams WHERE id = ?', (exam_id,))
        except sqlite3.IntegrityError:
            with connection:
                connection.execute('UPDATE exams SET archived = 1 WHERE id = ?', (exam_id,))
            flash('Referenced exam archived; its history remains accessible.')
        else:
            flash('Unused Draft exam deleted.')
    return redirect(url_for('admin.exams'))


def numeric_search_id(query):
    if re.fullmatch(r'[0-9]{1,19}', query):
        value = int(query)
        if 0 < value <= 9223372036854775807:
            return value
    return None


@bp.get('/people')
@role_required('Admin', ('Active',))
def people():
    query = request.args.get('q', '').strip()
    rows = get_db().execute(
        "SELECT id, name, email, role, status, contact, department FROM users "
        "WHERE role IN ('Student', 'Examiner') "
        'AND (? = ? OR instr(lower(name), lower(?)) > 0 OR id = ?) ORDER BY role, name, id',
        (query, '', query, numeric_search_id(query)),
    ).fetchall()
    return render_template('admin/people.html', people=rows, query=query)


@bp.route('/people/examiners/new', methods=('GET', 'POST'))
@role_required('Admin', ('Active',))
def create_examiner():
    errors = []
    if request.method == 'POST':
        data, errors = validate_account(request.form)
        if not errors:
            connection = get_db()
            try:
                with connection:
                    insert_account(connection, data, 'Examiner', 'Approved')
            except sqlite3.IntegrityError:
                errors.append('That email is already registered. Use another email.')
            else:
                flash('Approved Examiner account created.')
                return redirect(url_for('admin.people'))
    return render_template('auth/register.html', role='Examiner', admin_create=True, errors=errors), 400 if errors else 200


def get_examiner(user_id):
    if not 0 < user_id <= 9223372036854775807:
        abort(404, description='Examiner not found.')
    user = get_db().execute("SELECT * FROM users WHERE id = ? AND role = 'Examiner'", (user_id,)).fetchone()
    if user is None:
        abort(404, description='Examiner not found.')
    return user


@bp.post('/people/<int:user_id>/approve')
@role_required('Admin', ('Active',))
def approve_examiner(user_id):
    connection = get_db()
    with connection:
        connection.execute('BEGIN IMMEDIATE')
        examiner = get_examiner(user_id)
        if examiner['status'] != 'Pending':
            abort(400, description='Only Pending examiners can be approved.')
        connection.execute("UPDATE users SET status = 'Approved' WHERE id = ?", (user_id,))
    flash('Examiner approved.')
    return redirect(url_for('admin.people'))


@bp.post('/people/<int:user_id>/deactivate')
@role_required('Admin', ('Active',))
def deactivate_examiner(user_id):
    connection = get_db()
    with connection:
        connection.execute('BEGIN IMMEDIATE')
        examiner = get_examiner(user_id)
        if examiner['status'] == 'Inactive':
            abort(400, description='This examiner is already inactive.')
        connection.execute("UPDATE users SET status = 'Inactive' WHERE id = ?", (user_id,))
    flash('Examiner deactivated. Existing assignments are retained for history.')
    return redirect(url_for('admin.people'))


def get_active_exam(exam_id):
    exam = get_exam(exam_id)
    if exam['archived']:
        abort(403, description='Archived exams are read-only.')
    return exam


def render_exam_detail(exam_id, errors=None, status=200):
    exam = get_exam(exam_id)
    connection = get_db()
    assignments = connection.execute(
        'SELECT users.id, users.name, users.status FROM examiner_assignments '
        'JOIN users ON users.id = examiner_assignments.examiner_id WHERE exam_id = ? ORDER BY users.name', (exam_id,),
    ).fetchall()
    eligible = connection.execute(
        "SELECT id, name FROM users WHERE role = 'Examiner' AND status = 'Approved' "
        'AND NOT EXISTS (SELECT 1 FROM examiner_assignments WHERE exam_id = ? AND examiner_id = users.id) ORDER BY name', (exam_id,),
    ).fetchall()
    rubrics = connection.execute('SELECT * FROM rubrics WHERE exam_id = ? ORDER BY id', (exam_id,)).fetchall()
    total = sum(row['maximum_marks'] for row in rubrics)
    return render_template('admin/exam_detail.html', exam=exam, phases=PHASES, assignments=assignments,
                           eligible=eligible, rubrics=rubrics, rubric_total=total, errors=errors), status


@bp.post('/exams/<int:exam_id>/assign')
@role_required('Admin', ('Active',))
def assign_examiner(exam_id):
    examiner_id = numeric_search_id(request.form.get('examiner_id', '').strip())
    errors = []
    connection = get_db()
    with connection:
        connection.execute('BEGIN IMMEDIATE')
        get_active_exam(exam_id)
        examiner = connection.execute("SELECT id FROM users WHERE id = ? AND role = 'Examiner' AND status = 'Approved'", (examiner_id,)).fetchone()
        if examiner is None:
            errors.append('Choose an Approved Examiner account.')
        else:
            try:
                connection.execute('INSERT INTO examiner_assignments (exam_id, examiner_id) VALUES (?, ?)', (exam_id, examiner_id))
            except sqlite3.IntegrityError:
                errors.append('This examiner is already assigned to this exam.')
    if errors:
        return render_exam_detail(exam_id, errors, 400)
    flash('Examiner assigned.')
    return redirect(url_for('admin.exam_detail', exam_id=exam_id))


def get_criterion(exam_id, criterion_id):
    if not 0 < criterion_id <= 9223372036854775807:
        abort(404, description='Criterion not found in this exam.')
    criterion = get_db().execute('SELECT * FROM rubrics WHERE id = ? AND exam_id = ?', (criterion_id, exam_id)).fetchone()
    if criterion is None:
        abort(404, description='Criterion not found in this exam.')
    return criterion


@bp.route('/exams/<int:exam_id>/rubrics/new', methods=('GET', 'POST'))
@bp.route('/exams/<int:exam_id>/rubrics/<int:criterion_id>/edit', methods=('GET', 'POST'))
@role_required('Admin', ('Active',))
def rubric_form(exam_id, criterion_id=None):
    exam = get_active_exam(exam_id)
    criterion = get_criterion(exam_id, criterion_id) if criterion_id is not None else None
    values = dict(request.form) if request.method == 'POST' else dict(criterion or {})
    errors = []
    if request.method == 'POST':
        name = values.get('name', '').strip()
        description = values.get('description', '').strip()
        if not 1 <= len(name) <= 100 or len(description) > 2000:
            errors.append('Criterion name must contain 1–100 characters; description at most 2000.')
        try:
            maximum = int(values.get('maximum_marks', ''))
            if not 1 <= maximum <= 10000:
                raise ValueError
        except ValueError:
            errors.append('Criterion maximum must be a whole number between 1 and 10000.')
        if not errors:
            connection = get_db()
            with connection:
                connection.execute('BEGIN IMMEDIATE')
                exam = get_active_exam(exam_id)
                if criterion_id is not None:
                    get_criterion(exam_id, criterion_id)
                total = connection.execute('SELECT coalesce(sum(maximum_marks), 0) FROM rubrics WHERE exam_id = ? AND id != ?', (exam_id, criterion_id or 0)).fetchone()[0]
                if total + maximum > exam['maximum_marks']:
                    errors.append('Rubric total cannot exceed the exam maximum.')
                else:
                    try:
                        if criterion is None:
                            connection.execute('INSERT INTO rubrics (exam_id, name, maximum_marks, description) VALUES (?, ?, ?, ?)', (exam_id, name, maximum, description))
                        else:
                            connection.execute('UPDATE rubrics SET name = ?, maximum_marks = ?, description = ? WHERE id = ? AND exam_id = ?', (name, maximum, description, criterion_id, exam_id))
                    except sqlite3.IntegrityError:
                        errors.append('That criterion name is already used in this exam.')
            if not errors:
                flash('Rubric criterion saved.')
                return redirect(url_for('admin.exam_detail', exam_id=exam_id))
    return render_template('admin/rubric_form.html', exam=exam, criterion=criterion, values=values, errors=errors), 400 if errors else 200


@bp.post('/exams/<int:exam_id>/rubrics/<int:criterion_id>/delete')
@role_required('Admin', ('Active',))
def delete_criterion(exam_id, criterion_id):
    connection = get_db()
    with connection:
        connection.execute('BEGIN IMMEDIATE')
        get_active_exam(exam_id)
        get_criterion(exam_id, criterion_id)
        connection.execute('DELETE FROM rubrics WHERE id = ? AND exam_id = ?', (criterion_id, exam_id))
    flash('Rubric criterion deleted.')
    return redirect(url_for('admin.exam_detail', exam_id=exam_id))
