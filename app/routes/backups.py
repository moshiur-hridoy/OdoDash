"""Scheduled backups: the admin's schedule and each account's copies (#29)."""
from flask import Blueprint, abort, flash, redirect, request, send_file, url_for
from flask_babel import gettext as _
from flask_login import current_user, login_required

from app.models import AppSettings
from app.security import admin_required
from app.services import scheduled_backup

bp = Blueprint('backups', __name__, url_prefix='/backups')


def _back_to_settings():
    return redirect(url_for('auth.settings') + '#integrations')


@bp.route('/schedule', methods=['POST'])
@login_required
@admin_required
def schedule():
    """Set how often backups run and how many are kept (admin only)."""
    frequency = request.form.get('backup_frequency')
    keep = request.form.get('backup_keep', type=int)
    if (frequency not in scheduled_backup.FREQUENCIES
            or keep is None or not 1 <= keep <= scheduled_backup.MAX_KEEP):
        flash(_('Choose how often to back up, and keep between 1 and %(max)d copies.')
              % {'max': scheduled_backup.MAX_KEEP}, 'error')
        return _back_to_settings()

    AppSettings.set(scheduled_backup.SETTING_FREQUENCY, frequency)
    AppSettings.set(scheduled_backup.SETTING_KEEP, str(keep))
    flash(_('Backup schedule saved'), 'success')
    return _back_to_settings()


@bp.route('/<filename>')
@login_required
def download(filename):
    path = scheduled_backup.backup_path(current_user, filename)
    if path is None:
        abort(404)
    return send_file(path, mimetype='application/zip', as_attachment=True,
                     download_name=filename, max_age=0)


@bp.route('/<filename>/delete', methods=['POST'])
@login_required
def delete(filename):
    if not scheduled_backup.delete_backup(current_user, filename):
        abort(404)
    flash(_('Backup deleted'), 'success')
    return _back_to_settings()
