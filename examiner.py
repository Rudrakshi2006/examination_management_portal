from flask import Blueprint, g, render_template
from auth import role_required
from db import get_db

bp = Blueprint('examiner', __name__, url_prefix='/examiner')


@bp.get('/dashboard')
@role_required('Examiner', ('Approved',))
def dashboard():
    exams = get_db().execute(
        'SELECT exams.*, courses.code AS course_code FROM examiner_assignments '
        'JOIN exams ON exams.id = examiner_assignments.exam_id '
        'JOIN courses ON courses.id = exams.course_id WHERE examiner_id = ? '
        'ORDER BY exams.archived, exams.id DESC', (g.user['id'],),
    ).fetchall()
    return render_template('examiner/dashboard.html', exams=exams)


@bp.get('/pending')
@role_required('Examiner', ('Pending',))
def pending():
    return render_template('examiner/pending.html')
