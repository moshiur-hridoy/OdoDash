"""Build a user's full backup archive.

The ZIP holds ``data.json`` (every record), ``manifest.json`` (each stored file
with its size and SHA-256) and the user's uploaded files under ``uploads/``.

It used to be written inside the ``/api/export/backup`` view, which tied it to
``current_user`` and a request. A scheduled backup (#29) has neither, so the
builder takes the user and the upload folder as arguments and writes to
whatever ``zipfile.ZipFile`` accepts: a path or a file object. The view and the
scheduler share this one exporter.
"""
import hashlib
import json
import os
import zipfile

from app.models import ChargingSession, Expense, FuelLog, Trip
from app.utils import utcnow
from config import APP_VERSION


def build_full_backup(user, upload_folder, out):
    """Write ``user``'s full backup ZIP to ``out`` (a path or a binary file object).

    Files that are listed in the database but missing or unreadable on disk are
    left out of the archive and the manifest rather than failing the backup.
    """
    # Build export data (similar to export_json but with attachment info)
    export_data = {
        'export_info': {
            'exported_at': utcnow().isoformat(),
            'username': user.username,
            'app_version': APP_VERSION,
            'backup_type': 'full'
        },
        'user_preferences': {
            'language': user.language,
            'distance_unit': user.distance_unit,
            'volume_unit': user.volume_unit,
            'consumption_unit': user.consumption_unit,
            'currency': user.currency
        },
        'vehicles': [],
        'fuel_stations': [],
        'fuel_price_history': []
    }

    # Track files to include
    files_to_backup = []  # List of (filename, file_type, record_type, record_id)

    for vehicle in user.get_all_vehicles():
        vehicle_data = {
            'id': vehicle.id,
            'name': vehicle.name,
            'vehicle_type': vehicle.vehicle_type,
            'make': vehicle.make,
            'model': vehicle.model,
            'year': vehicle.year,
            'registration': vehicle.registration,
            'vin': vehicle.vin,
            'fuel_type': vehicle.fuel_type,
            'tank_capacity': vehicle.tank_capacity,
            'starting_odometer': vehicle.starting_odometer,
            'odometer_unit': vehicle.odometer_unit,
            'tracking_unit': vehicle.tracking_unit,
            'battery_capacity': vehicle.battery_capacity,
            'is_active': vehicle.is_active,
            'notes': vehicle.notes,
            'image_filename': vehicle.image_filename,
            'mot_status': vehicle.mot_status,
            'mot_expiry': vehicle.mot_expiry.isoformat() if vehicle.mot_expiry else None,
            'tax_status': vehicle.tax_status,
            'tax_due': vehicle.tax_due.isoformat() if vehicle.tax_due else None,
            'created_at': vehicle.created_at.isoformat() if vehicle.created_at else None,
            'specifications': [],
            'fuel_logs': [],
            'expenses': [],
            'reminders': [],
            'maintenance_schedules': [],
            'maintenance_events': [event.to_dict() for event in vehicle.maintenance_events.all()],
            'tire_sets': [tire_set.to_dict() for tire_set in vehicle.tire_sets.all()],
            'recurring_expenses': [],
            'documents': [],
            'trips': [],
            'charging_sessions': [],
            'parts': [],
            'attachments': []
        }

        # Track vehicle image
        if vehicle.image_filename:
            files_to_backup.append((vehicle.image_filename, 'image', 'vehicle', vehicle.id))

        # Add vehicle attachments
        for attachment in vehicle.attachments.all():
            vehicle_data['attachments'].append({
                'id': attachment.id,
                'filename': attachment.filename,
                'original_filename': attachment.original_filename,
                'file_type': attachment.file_type,
                'file_size': attachment.file_size,
                'description': attachment.description,
                'created_at': attachment.created_at.isoformat() if attachment.created_at else None
            })
            files_to_backup.append((attachment.filename, attachment.file_type, 'vehicle_attachment', attachment.id))

        # Add specifications
        for spec in vehicle.specs.all():
            vehicle_data['specifications'].append({
                'id': spec.id,
                'spec_type': spec.spec_type,
                'label': spec.label,
                'value': spec.value,
                'created_at': spec.created_at.isoformat() if spec.created_at else None
            })

        # Add fuel logs with attachments
        for log in vehicle.fuel_logs.order_by(FuelLog.date.desc(), FuelLog.odometer.desc()).all():
            log_data = {
                'id': log.id,
                'date': log.date.isoformat() if log.date else None,
                'odometer': log.odometer,
                'odometer_confirmed': log.odometer_confirmed,
                'volume': log.volume,
                'price_per_unit': log.price_per_unit,
                'total_cost': log.total_cost,
                'sales_tax': log.sales_tax,
                'fuel_type': log.fuel_type,
                'fuel_distance': log.fuel_distance,
                'is_full_tank': log.is_full_tank,
                'is_missed': log.is_missed,
                'station': log.station,
                'notes': log.notes,
                'created_at': log.created_at.isoformat() if log.created_at else None,
                'attachments': []
            }
            for attachment in log.attachments.all():
                log_data['attachments'].append({
                    'id': attachment.id,
                    'filename': attachment.filename,
                    'original_filename': attachment.original_filename,
                    'file_type': attachment.file_type,
                    'file_size': attachment.file_size,
                    'description': attachment.description,
                    'created_at': attachment.created_at.isoformat() if attachment.created_at else None
                })
                files_to_backup.append((attachment.filename, attachment.file_type, 'fuel_log_attachment', attachment.id))
            vehicle_data['fuel_logs'].append(log_data)

        # Add expenses with attachments
        for expense in vehicle.expenses.order_by(Expense.date.desc()).all():
            expense_data = {
                'id': expense.id,
                'date': expense.date.isoformat() if expense.date else None,
                'category': expense.category,
                'description': expense.description,
                'cost': expense.cost,
                'odometer': expense.odometer,
                'vendor': expense.vendor,
                'notes': expense.notes,
                'created_at': expense.created_at.isoformat() if expense.created_at else None,
                'attachments': []
            }
            for attachment in expense.attachments.all():
                expense_data['attachments'].append({
                    'id': attachment.id,
                    'filename': attachment.filename,
                    'original_filename': attachment.original_filename,
                    'file_type': attachment.file_type,
                    'file_size': attachment.file_size,
                    'description': attachment.description,
                    'created_at': attachment.created_at.isoformat() if attachment.created_at else None
                })
                files_to_backup.append((attachment.filename, attachment.file_type, 'expense_attachment', attachment.id))
            vehicle_data['expenses'].append(expense_data)

        # Add reminders
        for reminder in vehicle.reminders.all():
            vehicle_data['reminders'].append({
                'id': reminder.id,
                'title': reminder.title,
                'description': reminder.description,
                'reminder_type': reminder.reminder_type,
                'due_date': reminder.due_date.isoformat() if reminder.due_date else None,
                'recurrence': reminder.recurrence,
                'recurrence_interval': reminder.recurrence_interval,
                'notify_days_before': reminder.notify_days_before,
                'notification_sent': reminder.notification_sent,
                'is_completed': reminder.is_completed,
                'completed_at': reminder.completed_at.isoformat() if reminder.completed_at else None,
                'created_at': reminder.created_at.isoformat() if reminder.created_at else None
            })

        # Add maintenance schedules
        for schedule in vehicle.maintenance_schedules.all():
            vehicle_data['maintenance_schedules'].append({
                'id': schedule.id,
                'name': schedule.name,
                'maintenance_type': schedule.maintenance_type,
                'description': schedule.description,
                'interval_miles': schedule.interval_miles,
                'interval_km': schedule.interval_km,
                'interval_months': schedule.interval_months,
                'last_performed_date': schedule.last_performed_date.isoformat() if schedule.last_performed_date else None,
                'last_performed_odometer': schedule.last_performed_odometer,
                'next_due_date': schedule.next_due_date.isoformat() if schedule.next_due_date else None,
                'next_due_odometer': schedule.next_due_odometer,
                'estimated_cost': schedule.estimated_cost,
                'auto_remind': schedule.auto_remind,
                'remind_days_before': schedule.remind_days_before,
                'remind_miles_before': schedule.remind_miles_before,
                'is_active': schedule.is_active,
                'created_at': schedule.created_at.isoformat() if schedule.created_at else None
            })

        # Add recurring expenses
        for recurring in vehicle.recurring_expenses.all():
            vehicle_data['recurring_expenses'].append({
                'id': recurring.id,
                'name': recurring.name,
                'category': recurring.category,
                'description': recurring.description,
                'amount': recurring.amount,
                'vendor': recurring.vendor,
                'frequency': recurring.frequency,
                'start_date': recurring.start_date.isoformat() if recurring.start_date else None,
                'end_date': recurring.end_date.isoformat() if recurring.end_date else None,
                'last_generated': recurring.last_generated.isoformat() if recurring.last_generated else None,
                'next_due': recurring.next_due.isoformat() if recurring.next_due else None,
                'auto_create': recurring.auto_create,
                'notify_before_days': recurring.notify_before_days,
                'is_active': recurring.is_active,
                'created_at': recurring.created_at.isoformat() if recurring.created_at else None
            })

        # Add documents with filename for restore
        for doc in vehicle.documents.all():
            vehicle_data['documents'].append({
                'id': doc.id,
                'title': doc.title,
                'document_type': doc.document_type,
                'description': doc.description,
                'filename': doc.filename,
                'original_filename': doc.original_filename,
                'file_type': doc.file_type,
                'file_size': doc.file_size,
                'issue_date': doc.issue_date.isoformat() if doc.issue_date else None,
                'expiry_date': doc.expiry_date.isoformat() if doc.expiry_date else None,
                'reference_number': doc.reference_number,
                'remind_before_expiry': doc.remind_before_expiry,
                'remind_days': doc.remind_days,
                'created_at': doc.created_at.isoformat() if doc.created_at else None
            })
            files_to_backup.append((doc.filename, doc.file_type, 'document', doc.id))

        # Add trips
        for trip in vehicle.trips.order_by(Trip.date.desc()).all():
            vehicle_data['trips'].append({
                'id': trip.id,
                'date': trip.date.isoformat() if trip.date else None,
                'start_odometer': trip.start_odometer,
                'end_odometer': trip.end_odometer,
                'distance': trip.distance,
                'start_fuel_level': trip.start_fuel_level,
                'end_fuel_level': trip.end_fuel_level,
                'purpose': trip.purpose,
                'description': trip.description,
                'start_location': trip.start_location,
                'end_location': trip.end_location,
                'notes': trip.notes,
                'created_at': trip.created_at.isoformat() if trip.created_at else None
            })

        # Add charging sessions
        for session in vehicle.charging_sessions.order_by(ChargingSession.date.desc()).all():
            vehicle_data['charging_sessions'].append({
                'id': session.id,
                'date': session.date.isoformat() if session.date else None,
                'start_time': session.start_time.isoformat() if session.start_time else None,
                'end_time': session.end_time.isoformat() if session.end_time else None,
                'odometer': session.odometer,
                'kwh_added': session.kwh_added,
                'start_soc': session.start_soc,
                'end_soc': session.end_soc,
                'cost_per_kwh': session.cost_per_kwh,
                'total_cost': session.total_cost,
                'charger_type': session.charger_type,
                'location': session.location,
                'network': session.network,
                'notes': session.notes,
                'created_at': session.created_at.isoformat() if session.created_at else None
            })

        # Add vehicle parts
        for part in vehicle.parts.all():
            vehicle_data['parts'].append({
                'id': part.id,
                'name': part.name,
                'part_type': part.part_type,
                'specification': part.specification,
                'quantity': part.quantity,
                'unit': part.unit,
                'part_number': part.part_number,
                'supplier_url': part.supplier_url,
                'notes': part.notes,
                'created_at': part.created_at.isoformat() if part.created_at else None,
                'updated_at': part.updated_at.isoformat() if part.updated_at else None
            })

        export_data['vehicles'].append(vehicle_data)

    # Add fuel stations (not vehicle-specific)
    for station in user.fuel_stations.all():
        export_data['fuel_stations'].append({
            'id': station.id,
            'name': station.name,
            'brand': station.brand,
            'address': station.address,
            'city': station.city,
            'postcode': station.postcode,
            'latitude': station.latitude,
            'longitude': station.longitude,
            'notes': station.notes,
            'is_favorite': station.is_favorite,
            'price_source': station.price_source,
            'external_id': station.external_id,
            'times_used': station.times_used,
            'last_used': station.last_used.isoformat() if station.last_used else None,
            'created_at': station.created_at.isoformat() if station.created_at else None
        })

    # Add fuel price history
    for station in user.fuel_stations.all():
        for price in station.price_history.all():
            export_data['fuel_price_history'].append({
                'id': price.id,
                'station_id': station.id,
                'station_name': station.name,
                'date': price.date.isoformat() if price.date else None,
                'fuel_type': price.fuel_type,
                'price_per_unit': price.price_per_unit,
                'created_at': price.created_at.isoformat() if price.created_at else None
            })

    # Build manifest and create ZIP
    manifest = {
        'version': APP_VERSION,
        'created_at': utcnow().isoformat(),
        'username': user.username,
        'files': []
    }

    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add files to ZIP
        seen_files = set()
        for filename, file_type, record_type, record_id in files_to_backup:
            if not filename or filename in seen_files:
                continue
            seen_files.add(filename)

            file_path = os.path.join(upload_folder, filename)
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'rb') as f:
                        file_data = f.read()
                    file_hash = hashlib.sha256(file_data).hexdigest()
                    zf.writestr(f'uploads/{filename}', file_data)
                    manifest['files'].append({
                        'filename': filename,
                        'type': record_type,
                        'record_id': record_id,
                        'file_type': file_type,
                        'size': len(file_data),
                        'sha256': file_hash
                    })
                except (IOError, OSError):
                    # Skip files that can't be read
                    pass

        # Add manifest reference to export data
        export_data['files_manifest'] = {
            'total_files': len(manifest['files']),
            'files': manifest['files']
        }

        # Write data.json and manifest.json to ZIP
        zf.writestr('data.json', json.dumps(export_data, indent=2))
        zf.writestr('manifest.json', json.dumps(manifest, indent=2))
