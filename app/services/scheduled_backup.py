"""Scheduled full backups (#29).

An admin picks how often (off, daily or weekly) and how many copies to keep.
The hourly scheduler then writes, for every account that has data of its own,
the same ZIP as "Download ZIP" into that account's folder under
``BACKUP_FOLDER``. The folder is outside the uploads folder, so the only way to
a copy over the web is the signed-in account it belongs to.
"""
import logging
import os
import re
from collections import namedtuple
from datetime import datetime, timedelta

from flask import current_app

from app import db
from app.models import AppSettings, User
from app.services.backup_export import build_full_backup
from app.utils import utcnow
from config import Config

logger = logging.getLogger(__name__)

SETTING_FREQUENCY = 'backup_frequency'
SETTING_KEEP = 'backup_keep'

INTERVALS = {'daily': timedelta(days=1), 'weekly': timedelta(days=7)}
FREQUENCIES = ('off', *INTERVALS)
DEFAULT_KEEP = 7
MAX_KEEP = 30

# The scheduler wakes about once an hour. Without some slack, a copy that falls
# due a few seconds after a wake-up would wait a whole hour for the next one.
SLACK = timedelta(minutes=30)

FILENAME_RE = re.compile(r'ododash_backup_(\d{8}_\d{6})\.zip')
TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'

Backup = namedtuple('Backup', 'filename created size')


def get_frequency():
    value = AppSettings.get(SETTING_FREQUENCY, 'off')
    return value if value in FREQUENCIES else 'off'


def get_keep():
    try:
        value = int(AppSettings.get(SETTING_KEEP, DEFAULT_KEEP))
    except (TypeError, ValueError):
        return DEFAULT_KEEP
    return min(max(value, 1), MAX_KEEP)


def backup_root():
    return os.path.abspath(current_app.config.get('BACKUP_FOLDER') or Config.BACKUP_FOLDER)


def user_folder(user):
    """The folder holding ``user``'s copies.

    SQLite hands a deleted account's id to the next new account, so the name
    also carries the time the account was created.
    """
    created = user.created_at.strftime('%Y%m%d%H%M%S%f') if user.created_at else '0'
    return os.path.join(backup_root(), f'{user.id}-{created}')


def list_backups(user):
    """``user``'s copies, newest first."""
    folder = user_folder(user)
    try:
        names = os.listdir(folder)
    except FileNotFoundError:
        return []

    backups = []
    for name in sorted(names, reverse=True):
        match = FILENAME_RE.fullmatch(name)
        if not match:
            continue
        try:
            created = datetime.strptime(match.group(1), TIMESTAMP_FORMAT)
            size = os.path.getsize(os.path.join(folder, name))
        except (ValueError, OSError):
            continue
        backups.append(Backup(name, created, size))
    return backups


def backup_path(user, filename):
    """The path of one of ``user``'s copies, or None if they have no such copy."""
    if not FILENAME_RE.fullmatch(filename):
        return None
    path = os.path.join(user_folder(user), filename)
    return path if os.path.isfile(path) else None


def delete_backup(user, filename):
    path = backup_path(user, filename)
    if path is None:
        return False
    os.remove(path)
    return True


def remove_all_backups(folder):
    """Delete the copies in an account's folder, and the folder if that empties it.

    Takes the folder rather than the user so it can run after the account has
    been deleted. Anything this module did not write is left alone.
    """
    try:
        names = os.listdir(folder)
    except FileNotFoundError:
        return
    for name in names:
        if FILENAME_RE.fullmatch(name) or name.endswith('.partial'):
            os.remove(os.path.join(folder, name))
    if not os.listdir(folder):
        os.rmdir(folder)


def create_backup(user, now=None):
    """Write a new copy for ``user`` and return its file name.

    The archive is built under a temporary name and renamed once complete, so a
    full disk or a restart never leaves a broken file among the copies.
    """
    folder = user_folder(user)
    os.makedirs(folder, exist_ok=True)
    os.chmod(folder, 0o700)
    # Left behind by a run that was killed half way through.
    for name in os.listdir(folder):
        if name.endswith('.partial'):
            os.remove(os.path.join(folder, name))

    filename = f'ododash_backup_{(now or utcnow()).strftime(TIMESTAMP_FORMAT)}.zip'
    path = os.path.join(folder, filename)
    partial = f'{path}.partial'
    try:
        build_full_backup(user, current_app.config['UPLOAD_FOLDER'], partial)
        os.replace(partial, path)
    finally:
        if os.path.exists(partial):
            os.remove(partial)
    return filename


def prune_backups(user, keep, newest):
    """Keep ``newest`` and the ``keep - 1`` most recent of the other copies."""
    others = [backup for backup in list_backups(user) if backup.filename != newest]
    for backup in others[keep - 1:]:
        delete_backup(user, backup.filename)


def has_own_data(user):
    # An account that only sees vehicles shared with it needs no copy: they are
    # all in their owners' copies.
    return user.owned_vehicles.count() > 0 or user.fuel_stations.count() > 0


def run_scheduled_backups(now=None):
    """Write every copy that is due. Called by the hourly scheduler."""
    stats = {'created': 0, 'failed': 0}
    frequency = get_frequency()
    if frequency == 'off':
        return stats

    now = now or utcnow()
    keep = get_keep()
    for user in User.query.order_by(User.id).all():
        try:
            if not has_own_data(user):
                continue
            backups = list_backups(user)
            if backups and now - backups[0].created < INTERVALS[frequency] - SLACK:
                continue
            filename = create_backup(user, now)
            prune_backups(user, keep, filename)
            stats['created'] += 1
        except Exception:
            # One account's failure must not cost the others their copy. A
            # failed query would otherwise poison the session for the rest.
            logger.exception('Scheduled backup failed for user %s', user.id)
            db.session.rollback()
            stats['failed'] += 1
    return stats
