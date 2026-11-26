import sqlite3
from datetime import datetime, timedelta, timezone

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from auth import role_required
from db import get_db

bp = Blueprint('admin', __name__, url_prefix='/admin')
PHASES = ('Draft', 'Slot Creation', 'Booking Open', 'Closed', 'Completed')
TIMELINE_FIELDS = ('creation_start', 'creation_end', 'booking_start', 'booking_end')
IST = timezone(timedelta(hours=5, minutes=30))


def now_ist():
    return datetime.now(IST).replace(tzinfo=None).isoformat(timespec='minutes')


def get_course(course_id):
    course = get_db().execute('SELECT * FROM courses WHERE id = ?', (course_id,)).fetchone()
    if course is None:
        abort(404, description='Course not found.')
    return course


def get_exam(exam_id):
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
    rows = get_db().execute(
        'SELECT exams.*, courses.code AS course_code FROM exams '
        'JOIN courses ON courses.id = exams.course_id ORDER BY exams.archived, exams.id DESC'
    ).fetchall()
    return render_template('admin/exams.html', exams=rows)


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
        data, errors = validate_exam(values, exam)
        if not errors:
            fields = ('course_id', 'name', 'exam_type', 'duration_minutes', 'maximum_marks') + TIMELINE_FIELDS
            parameters = tuple(data[field] for field in fields)
            connection = get_db()
            with connection:
                if exam is None:
                    cursor = connection.execute(
                        'INSERT INTO exams (course_id, name, exam_type, duration_minutes, maximum_marks, creation_start, creation_end, booking_start, booking_end) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', parameters,
                    )
                    exam_id = cursor.lastrowid
                else:
                    connection.execute(
                        'UPDATE exams SET course_id = ?, name = ?, exam_type = ?, duration_minutes = ?, maximum_marks = ?, creation_start = ?, creation_end = ?, booking_start = ?, booking_end = ? WHERE id = ?', parameters + (exam_id,),
                    )
            flash('Exam saved. All timeline times are IST.')
            return redirect(url_for('admin.exam_detail', exam_id=exam_id))
    available_courses = get_db().execute('SELECT * FROM courses ORDER BY archived, code').fetchall()
    return render_template('admin/exam_form.html', values=values, exam=exam, courses=available_courses, errors=errors), 400 if errors else 200


@bp.get('/exams/<int:exam_id>')
@role_required('Admin', ('Active',))
def exam_detail(exam_id):
    return render_template('admin/exam_detail.html', exam=get_exam(exam_id), phases=PHASES)


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
        return render_template('admin/exam_detail.html', exam=exam, phases=PHASES, errors=errors), 400
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
