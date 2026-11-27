"""Rules for the files kept in the uploads folder.

One folder holds every account's files, and a record points at its file by
name alone. So a name taken from outside (a backup, for one) must never be
trusted to be free, and a file may only be removed once nothing points at it.
"""
import os

from sqlalchemy import func, or_

from app import db
from app.models import AppSettings, Attachment, Document, Expense, FuelLog, Vehicle

# Types a browser may show from the app's own address. Anything else is sent as
# a download. SVG is here for the instance logo and is sandboxed like the rest.
INLINE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf', 'svg'}

# Types that cannot run script, so need no sandbox (a sandbox would also stop
# the browser's PDF viewer).
SCRIPTLESS_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf'}

BRANDING_FILE_KEYS = ('logo_filename', 'favicon_filename')


def extension_of(filename):
    return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''


def upload_references(filename):
    """Every record pointing at ``filename``, as ``(stored_name, owner_id)``.

    The owner is the owner of the record's vehicle, or None for the instance
    branding. Matching ignores case, because some filesystems do.
    """
    if not filename:
        return []

    def matches(column):
        # The exact test as well: SQLite's lower() only folds ASCII
        return or_(column == filename, func.lower(column) == filename.lower())

    queries = [
        db.session.query(Vehicle.image_filename, Vehicle.owner_id)
        .filter(matches(Vehicle.image_filename)),
        db.session.query(Document.filename, Vehicle.owner_id)
        .outerjoin(Vehicle, Document.vehicle_id == Vehicle.id)
        .filter(matches(Document.filename)),
        db.session.query(AppSettings.value, db.null())
        .filter(AppSettings.key.in_(BRANDING_FILE_KEYS), matches(AppSettings.value)),
    ]
    references = [tuple(row) for query in queries for row in query.all()]

    for attachment in Attachment.query.filter(matches(Attachment.filename)).all():
        vehicle_id = attachment.vehicle_id
        for model, record_id in ((FuelLog, attachment.fuel_log_id),
                                 (Expense, attachment.expense_id)):
            if vehicle_id is None and record_id is not None:
                record = db.session.get(model, record_id)
                vehicle_id = record.vehicle_id if record else None
        vehicle = db.session.get(Vehicle, vehicle_id) if vehicle_id is not None else None
        references.append((attachment.filename, vehicle.owner_id if vehicle else None))

    return references


def remove_unused_upload(upload_folder, filename):
    """Delete an uploaded file once no record points at it.

    Call this after the record that used the file has been removed or changed.
    """
    if not filename or upload_references(filename):
        return
    path = os.path.join(upload_folder, filename)
    if os.path.isfile(path):
        os.remove(path)
