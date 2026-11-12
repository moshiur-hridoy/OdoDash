"""Design-system reference page.

Renders every component from templates/components/ui.html in place, with
sample content, so the system can be reviewed in both themes and at phone
width without hunting through the app. Administrators only: it is a
developer reference, not a feature, and its sample figures are not the
user's data. It reads nothing from the database.
"""
from flask import Blueprint, abort, render_template
from flask_login import current_user, login_required

bp = Blueprint('design', __name__, url_prefix='/design')


@bp.route('/')
@login_required
def index():
    if not current_user.is_admin:
        abort(403)
    return render_template('design/index.html')
