"""Which records keep an account from being deleted.

A record names the account that made it in a column that cannot be empty.
Deleting an account that still had such records ended in a server error. Where
nothing else pointed at the account, the delete went through instead and left
the rows behind: SQLite does not check foreign keys here, and it hands a deleted
account's id to the next new one.
"""
from flask_babel import lazy_gettext as _l

from app import db
from app.models import User, vehicle_users

# Table name to the name the administrator is shown, in the order listed.
RECORD_LABELS = {
    'vehicles': _l('Vehicles'),
    'fuel_logs': _l('Fuel Logs'),
    'expenses': _l('Expenses'),
    'trips': _l('Trips'),
    'trip_templates': _l('Trip Templates'),
    'charging_sessions': _l('Charging Sessions'),
    'reminders': _l('Reminders'),
    'maintenance_schedules': _l('Maintenance Schedules'),
    'maintenance_events': _l('Maintenance History'),
    'recurring_expenses': _l('Recurring Expenses'),
    'documents': _l('Documents'),
    'vehicle_parts': _l('Parts'),
    'tire_sets': _l('Tires'),
    'notes': _l('Notes'),
    'mileage_allowances': _l('Mileage Allowance'),
    'fuel_stations': _l('Fuel Stations'),
    'fuel_price_history': _l('Price History'),
}


def remaining_records(user):
    """``[(label, count), ...]`` for the records that still belong to ``user``.

    The tables are found from the schema, so a new one counts without being
    added here. Access to someone else's vehicle is not a record: it is removed
    along with the account.
    """
    counts = {}
    for table in db.metadata.tables.values():
        if table is vehicle_users:
            continue
        owner_columns = [fk.parent for fk in table.foreign_keys
                         if fk.column.table is User.__table__]
        if not owner_columns:
            continue
        count = db.session.scalar(
            db.select(db.func.count()).select_from(table)
            .where(db.or_(*(column == user.id for column in owner_columns))))
        if count:
            counts[table.name] = count

    order = list(RECORD_LABELS)
    names = sorted(counts, key=lambda name: order.index(name) if name in order else len(order))
    return [(RECORD_LABELS.get(name, name), counts[name]) for name in names]
