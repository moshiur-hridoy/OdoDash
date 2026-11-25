"""Tax Token, Fitness Certificate and Route Permit (#39).

The three types a Bangladesh vehicle owner has to renew can be chosen on the
reminder and document forms, are saved and shown with their names, and survive
the JSON export, the full backup and a restore into another account. Existing
types are untouched.
"""
import io
import json

import pytest

from app import db
from app.models import (
    DOCUMENT_TYPES, REMINDER_EXPENSE_CATEGORIES, REMINDER_TYPES, Document,
    EXPENSE_CATEGORIES, Reminder, Vehicle,
)
from app.services.backup_restore import read_backup, restore_backup

NEW_TYPES = {
    'tax_token': 'Tax Token',
    'fitness_certificate': 'Fitness Certificate',
    'route_permit': 'Route Permit',
}


class TestTypeLists:
    def test_reminder_types_include_the_three_keys(self):
        keys = [key for key, _ in REMINDER_TYPES]
        for key in NEW_TYPES:
            assert keys.count(key) == 1

    def test_document_types_include_the_three_keys(self):
        keys = [key for key, _ in DOCUMENT_TYPES]
        for key in NEW_TYPES:
            assert keys.count(key) == 1

    def test_existing_types_are_unchanged(self):
        reminder_keys = {key for key, _ in REMINDER_TYPES}
        document_keys = {key for key, _ in DOCUMENT_TYPES}
        assert {'mot', 'service', 'insurance', 'tax', 'registration', 'warranty',
                'tire_change', 'oil_change', 'custom'} <= reminder_keys
        assert {'insurance', 'registration', 'mot', 'service_record', 'purchase',
                'warranty', 'manual', 'other'} <= document_keys

    def test_labels_are_the_issue_names(self):
        assert {k: str(v) for k, v in REMINDER_TYPES if k in NEW_TYPES} == NEW_TYPES
        assert {k: str(v) for k, v in DOCUMENT_TYPES if k in NEW_TYPES} == NEW_TYPES

    def test_expense_category_for_each_reminder_is_a_real_category(self):
        categories = {key for key, _ in EXPENSE_CATEGORIES}
        for key in NEW_TYPES:
            assert REMINDER_EXPENSE_CATEGORIES[key] in categories


class TestReminderForm:
    def test_form_offers_the_three_types(self, auth_client, sample_vehicle):
        html = auth_client.get('/reminders/new').get_data(as_text=True)
        for key, label in NEW_TYPES.items():
            assert f'value="{key}"' in html
            assert label in html

    @pytest.mark.parametrize('key,label', NEW_TYPES.items())
    def test_create_saves_and_shows_the_type(self, auth_client, sample_vehicle, key, label):
        resp = auth_client.post('/reminders/new', data={
            'vehicle_id': str(sample_vehicle.id),
            'title': f'Renew {label}',
            'reminder_type': key,
            'due_date': '2030-01-15',
            'recurrence': 'none',
            'notify_days_before': '14',
        }, follow_redirects=True)
        assert resp.status_code == 200

        reminder = Reminder.query.filter_by(title=f'Renew {label}').one()
        assert reminder.reminder_type == key
        assert reminder.to_dict()['reminder_type'] == key

        index = auth_client.get('/reminders/').get_data(as_text=True)
        assert f'Renew {label}' in index
        # The badge shows the translated name, not the raw key.
        assert f'>{label}<' in index or label in index.replace(f'Renew {label}', '')

    @pytest.mark.parametrize('key,label', NEW_TYPES.items())
    def test_type_can_be_edited_to(self, auth_client, sample_vehicle, test_user, key, label):
        from datetime import date
        reminder = Reminder(vehicle_id=sample_vehicle.id, user_id=test_user.id,
                            title='Paper', reminder_type='custom',
                            due_date=date(2030, 1, 1), recurrence='none',
                            notify_days_before=7)
        db.session.add(reminder)
        db.session.commit()

        resp = auth_client.post(f'/reminders/{reminder.id}/edit', data={
            'title': 'Paper',
            'reminder_type': key,
            'due_date': '2030-01-01',
            'recurrence': 'none',
            'notify_days_before': '7',
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert db.session.get(Reminder, reminder.id).reminder_type == key

    def test_filter_by_new_type(self, auth_client, sample_vehicle, test_user):
        from datetime import date
        for title, rtype in (('Token', 'tax_token'), ('Oil', 'oil_change')):
            db.session.add(Reminder(vehicle_id=sample_vehicle.id, user_id=test_user.id,
                                    title=title, reminder_type=rtype,
                                    due_date=date(2030, 1, 1), recurrence='none',
                                    notify_days_before=7))
        db.session.commit()
        html = auth_client.get('/reminders/?type=tax_token').get_data(as_text=True)
        assert 'Token' in html
        assert 'Oil' not in html.split('<main')[-1].replace('Oil Change', '')


class TestDocumentForm:
    def test_form_offers_the_three_types(self, auth_client, sample_vehicle):
        html = auth_client.get('/documents/new').get_data(as_text=True)
        for key, label in NEW_TYPES.items():
            assert f'value="{key}"' in html
            assert label in html

    @pytest.mark.parametrize('key,label', NEW_TYPES.items())
    def test_upload_saves_and_shows_the_type(self, auth_client, sample_vehicle, key, label):
        resp = auth_client.post('/documents/new', data={
            'vehicle_id': str(sample_vehicle.id),
            'title': f'My {label}',
            'document_type': key,
            'file': (io.BytesIO(b'%PDF-1.4 scan'), 'scan.pdf'),
        }, content_type='multipart/form-data', follow_redirects=True)
        assert resp.status_code == 200

        doc = Document.query.filter_by(title=f'My {label}').one()
        assert doc.document_type == key

        view = auth_client.get(f'/documents/{doc.id}').get_data(as_text=True)
        assert label in view
        assert key not in view.split('<main')[-1]


class TestExportAndRestore:
    @pytest.fixture
    def papers(self, app, sample_vehicle, test_user):
        """One reminder and one document of each new type."""
        from datetime import date
        for key, label in NEW_TYPES.items():
            db.session.add(Reminder(vehicle_id=sample_vehicle.id, user_id=test_user.id,
                                    title=f'{label} due', reminder_type=key,
                                    due_date=date(2030, 3, 1), recurrence='yearly',
                                    notify_days_before=30))
            db.session.add(Document(vehicle_id=sample_vehicle.id, user_id=test_user.id,
                                    title=f'{label} copy', document_type=key,
                                    filename=f'doc_{key}.pdf',
                                    original_filename=f'{key}.pdf',
                                    file_type='pdf', file_size=5))
        db.session.commit()

    def test_json_export_carries_the_type_keys(self, auth_client, papers):
        data = json.loads(auth_client.get('/api/export/json').data)
        vehicle = data['vehicles'][0]
        assert {r['reminder_type'] for r in vehicle['reminders']} == set(NEW_TYPES)
        assert {d['document_type'] for d in vehicle['documents']} == set(NEW_TYPES)

    def test_reminders_restore_into_another_account(self, auth_client, admin_user, papers):
        data = json.loads(auth_client.get('/api/export/json').data)
        restore_backup(data, admin_user)

        vehicle = Vehicle.query.filter_by(owner_id=admin_user.id).one()
        restored = {r.reminder_type: r.title for r in vehicle.reminders}
        assert restored == {key: f'{label} due' for key, label in NEW_TYPES.items()}

    def test_documents_restore_from_a_full_backup(self, auth_client, admin_user, papers,
                                                  tmp_path):
        exported = auth_client.get('/api/export/backup')
        assert exported.status_code == 200
        archive = tmp_path / 'backup.zip'
        archive.write_bytes(exported.data)

        # The export lists the files in the archive; give each one content so
        # the restore has something to copy.
        import zipfile
        with zipfile.ZipFile(archive, 'a') as zf:
            names = set(zf.namelist())
            for key in NEW_TYPES:
                name = f'uploads/doc_{key}.pdf'
                if name not in names:
                    zf.writestr(name, b'%PDF-1.4')

        data, zip_path = read_backup(str(archive))
        restore_backup(data, admin_user, zip_path=zip_path,
                       upload_folder=str(tmp_path / 'uploads'))

        vehicle = Vehicle.query.filter_by(owner_id=admin_user.id).one()
        restored = {d.document_type: d.title for d in vehicle.documents}
        assert restored == {key: f'{label} copy' for key, label in NEW_TYPES.items()}

    def test_restore_is_idempotent_for_the_new_types(self, auth_client, admin_user, papers):
        data = json.loads(auth_client.get('/api/export/json').data)
        restore_backup(data, admin_user)
        restore_backup(data, admin_user)
        vehicle = Vehicle.query.filter_by(owner_id=admin_user.id).one()
        assert vehicle.reminders.count() == 3
