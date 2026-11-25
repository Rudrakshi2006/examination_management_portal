from flask import Blueprint, render_template
from auth import role_required

bp = Blueprint('admin', __name__, url_prefix='/admin')


@bp.get('/dashboard')
@role_required('Admin', ('Active',))
def dashboard():
    return render_template('dashboard.html', role='Admin')
