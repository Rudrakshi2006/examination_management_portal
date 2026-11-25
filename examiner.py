from flask import Blueprint, render_template
from auth import role_required

bp = Blueprint('examiner', __name__, url_prefix='/examiner')


@bp.get('/dashboard')
@role_required('Examiner', ('Approved',))
def dashboard():
    return render_template('dashboard.html', role='Examiner')


@bp.get('/pending')
@role_required('Examiner', ('Pending',))
def pending():
    return render_template('examiner/pending.html')
