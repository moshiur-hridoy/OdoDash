"""The full backup ZIP, pinned before it moved out of the route (#29).

``/api/export/backup`` used to build the whole archive inside the view, tied to
``current_user``. A scheduled backup has no request, so the builder now lives in
``app.services.backup_export`` and the route only wraps it. These tests hold the
archive's content steady across that move: what goes in, how it is described and
whose data is left out.
"""
import hashlib
import io
import json
import os
import zipfile
from datetime import date

import pytest

from app import db
from app.models import (
    Attachment, ChargingSession, Document, Expense, FuelLog, FuelPriceHistory,
    FuelStation, Reminder, Trip, Vehicle, VehiclePart,
)

SECTIONS = ('fuel_logs', 'expenses', 'reminders', 'documents', 'trips',
            'charging_sessions', 'parts', 'attachments')


@pytest.fixture
def populated(app, test_user, sample_vehicle):
    """A vehicle with a row in every section, two of them with files on disk."""
    folder = app.config['UPLOAD_FOLDER']
    os.makedirs(folder, exist_ok=True)
    files = {'doc_pin_paper.pdf': b'%PDF-1.4 paper', 'veh_pin_photo.jpg': b'\xff\xd8photo'}
    for name, content in files.items():
        with open(os.path.join(folder, name), 'wb') as handle:
            handle.write(content)

    vehicle = sample_vehicle
    vehicle.image_filename = 'veh_pin_photo.jpg'
    db.session.add_all([
        FuelLog(vehicle_id=vehicle.id, user_id=test_user.id, date=date(2024, 1, 15),
                odometer=10000.0, volume=40.0, price_per_unit=1.5, total_cost=60.0,
                is_full_tank=True, station='Shell'),
        Expense(vehicle_id=vehicle.id, user_id=test_user.id, date=date(2024, 1, 20),
                category='maintenance', description='Oil change', cost=75.0),
        Reminder(vehicle_id=vehicle.id, user_id=test_user.id, title='MOT',
                 reminder_type='mot', due_date=date(2030, 3, 1), recurrence='yearly',
                 notify_days_before=30),
        Document(vehicle_id=vehicle.id, user_id=test_user.id, title='Paper',
                 document_type='other', filename='doc_pin_paper.pdf',
                 original_filename='paper.pdf', file_type='pdf', file_size=14),
        Trip(vehicle_id=vehicle.id, user_id=test_user.id, date=date(2024, 1, 25),
             start_odometer=10000.0, end_odometer=10050.0,
             purpose='business'),
        ChargingSession(vehicle_id=vehicle.id, user_id=test_user.id, date=date(2024, 1, 30),
                        odometer=10100.0, kwh_added=40.0, cost_per_kwh=0.3, total_cost=12.0),
        VehiclePart(vehicle_id=vehicle.id, user_id=test_user.id, name='Oil filter',
                    part_type='filter', part_number='OF-1', quantity=1.0),
    ])
    station = FuelStation(user_id=test_user.id, name='Shell Anytown', brand='Shell')
    db.session.add(station)
    db.session.commit()
    db.session.add(FuelPriceHistory(station_id=station.id, user_id=test_user.id,
                                    date=date(2024, 1, 15),
                                    fuel_type='petrol', price_per_unit=1.5))
    db.session.commit()
    return files


def _open(response):
    return zipfile.ZipFile(io.BytesIO(response.data))


class TestArchiveContent:
    def test_every_section_is_exported(self, auth_client, populated):
        with _open(auth_client.get('/api/export/backup')) as zf:
            data = json.loads(zf.read('data.json'))
        vehicle = data['vehicles'][0]
        for section in ('fuel_logs', 'expenses', 'reminders', 'documents', 'trips',
                        'charging_sessions', 'parts'):
            assert len(vehicle[section]) == 1, section
        assert data['export_info']['backup_type'] == 'full'
        assert data['export_info']['username']
        assert [s['name'] for s in data['fuel_stations']] == ['Shell Anytown']
        assert len(data['fuel_price_history']) == 1

    def test_files_are_stored_under_uploads(self, auth_client, populated):
        with _open(auth_client.get('/api/export/backup')) as zf:
            assert set(zf.namelist()) == {
                'data.json', 'manifest.json',
                'uploads/doc_pin_paper.pdf', 'uploads/veh_pin_photo.jpg'}
            for name, content in populated.items():
                assert zf.read(f'uploads/{name}') == content

    def test_manifest_describes_each_file(self, auth_client, populated):
        with _open(auth_client.get('/api/export/backup')) as zf:
            manifest = json.loads(zf.read('manifest.json'))
            data = json.loads(zf.read('data.json'))
        by_name = {entry['filename']: entry for entry in manifest['files']}
        assert set(by_name) == set(populated)
        for name, content in populated.items():
            assert by_name[name]['size'] == len(content)
            assert by_name[name]['sha256'] == hashlib.sha256(content).hexdigest()
        assert by_name['veh_pin_photo.jpg']['type'] == 'vehicle'
        assert by_name['doc_pin_paper.pdf']['type'] == 'document'
        assert data['files_manifest']['total_files'] == 2

    def test_a_missing_file_is_skipped_not_fatal(self, auth_client, app, populated):
        os.unlink(os.path.join(app.config['UPLOAD_FOLDER'], 'doc_pin_paper.pdf'))
        with _open(auth_client.get('/api/export/backup')) as zf:
            assert 'uploads/doc_pin_paper.pdf' not in zf.namelist()
            manifest = json.loads(zf.read('manifest.json'))
        assert [e['filename'] for e in manifest['files']] == ['veh_pin_photo.jpg']

    def test_download_headers(self, auth_client):
        resp = auth_client.get('/api/export/backup')
        assert resp.mimetype == 'application/zip'
        disposition = resp.headers['Content-Disposition']
        assert disposition.startswith('attachment; filename=may_full_backup_')
        assert disposition.endswith('.zip')


class TestOwnership:
    def test_another_users_vehicle_is_left_out(self, auth_client, admin_user, sample_vehicle):
        db.session.add(Vehicle(owner_id=admin_user.id, name='Not Yours',
                               vehicle_type='car', fuel_type='petrol'))
        db.session.commit()
        with _open(auth_client.get('/api/export/backup')) as zf:
            data = json.loads(zf.read('data.json'))
        assert [v['name'] for v in data['vehicles']] == ['Test Car']


class TestBuilderWithoutARequest:
    """What a scheduled backup relies on: no request, no logged-in user."""

    def test_writes_the_same_archive_to_a_path(self, app, test_user, populated, tmp_path):
        from app.services.backup_export import build_full_backup
        target = tmp_path / 'backup.zip'
        build_full_backup(test_user, app.config['UPLOAD_FOLDER'], str(target))
        with zipfile.ZipFile(target) as zf:
            assert set(zf.namelist()) == {
                'data.json', 'manifest.json',
                'uploads/doc_pin_paper.pdf', 'uploads/veh_pin_photo.jpg'}
            assert json.loads(zf.read('data.json'))['export_info']['username'] == test_user.username

    def test_writes_to_a_file_object(self, app, test_user, populated):
        from app.services.backup_export import build_full_backup
        buffer = io.BytesIO()
        build_full_backup(test_user, app.config['UPLOAD_FOLDER'], buffer)
        assert zipfile.is_zipfile(io.BytesIO(buffer.getvalue()))

    def test_the_archive_restores(self, app, test_user, admin_user, populated, tmp_path):
        from app.services.backup_export import build_full_backup
        from app.services.backup_restore import read_backup, restore_backup
        target = tmp_path / 'backup.zip'
        build_full_backup(test_user, app.config['UPLOAD_FOLDER'], str(target))
        data, zip_path = read_backup(str(target))
        restore_backup(data, admin_user, zip_path=zip_path,
                       upload_folder=str(tmp_path / 'uploads'))
        restored = Vehicle.query.filter_by(owner_id=admin_user.id).one()
        assert restored.fuel_logs.count() == 1
        assert restored.expenses.count() == 1
        assert restored.documents.count() == 1
