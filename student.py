from flask import Blueprint, render_template
from auth import role_required

bp = Blueprint('student', __name__, url_prefix='/student')


@bp.get('/dashboard')
@role_required('Student', ('Active',))
def dashboard():
    return render_template('dashboard.html', role='Student')
