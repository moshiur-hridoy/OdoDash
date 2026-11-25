"""Driving Licence as a reminder type and a document type (#40, option 1).

A licence belongs to a person, but a reminder needs a vehicle today, so it is
filed under one of the owner's vehicles. No new data model: one reminder type
and one document type.
"""
import io
import json
from datetime import date

from app import db
from app.models import (
    DOCUMENT_TYPES, EXPENSE_CATEGORIES, REMINDER_EXPENSE_CATEGORIES,
    REMINDER_TYPES, Document, Reminder, Vehicle,
)
from app.services.backup_restore import restore_backup

KEY = 'driving_licence'
LABEL = 'Driving Licence'


class TestTypeLists:
    def test_reminder_type_is_listed_once(self):
        assert [k for k, _ in REMINDER_TYPES].count(KEY) == 1
        assert str(dict(REMINDER_TYPES)[KEY]) == LABEL

    def test_document_type_is_listed_once(self):
        assert [k for k, _ in DOCUMENT_TYPES].count(KEY) == 1
        assert str(dict(DOCUMENT_TYPES)[KEY]) == LABEL

    def test_expense_category_is_a_real_one(self):
        assert REMINDER_EXPENSE_CATEGORIES[KEY] in {k for k, _ in EXPENSE_CATEGORIES}

    def test_other_types_are_unchanged(self):
        reminder_keys = {k for k, _ in REMINDER_TYPES}
        document_keys = {k for k, _ in DOCUMENT_TYPES}
        assert {'mot', 'tax', 'tax_token', 'fitness_certificate', 'route_permit',
                'custom'} <= reminder_keys
        assert {'insurance', 'mot', 'tax_token', 'other'} <= document_keys


class TestForms:
    def test_reminder_form_offers_it(self, auth_client, sample_vehicle):
        html = auth_client.get('/reminders/new').get_data(as_text=True)
        assert f'value="{KEY}"' in html
        assert LABEL in html

    def test_document_form_offers_it(self, auth_client, sample_vehicle):
        html = auth_client.get('/documents/new').get_data(as_text=True)
        assert f'value="{KEY}"' in html
        assert LABEL in html

    def test_create_reminder(self, auth_client, sample_vehicle):
        resp = auth_client.post('/reminders/new', data={
            'vehicle_id': str(sample_vehicle.id),
            'title': 'Renew licence',
            'reminder_type': KEY,
            'due_date': '2031-05-20',
            'recurrence': 'none',
            'notify_days_before': '30',
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert Reminder.query.filter_by(title='Renew licence').one().reminder_type == KEY
        assert LABEL in auth_client.get('/reminders/').get_data(as_text=True)

    def test_upload_document(self, auth_client, sample_vehicle):
        resp = auth_client.post('/documents/new', data={
            'vehicle_id': str(sample_vehicle.id),
            'title': 'Licence scan',
            'document_type': KEY,
            'file': (io.BytesIO(b'%PDF-1.4 scan'), 'licence.pdf'),
        }, content_type='multipart/form-data', follow_redirects=True)
        assert resp.status_code == 200
        doc = Document.query.filter_by(title='Licence scan').one()
        assert doc.document_type == KEY
        assert LABEL in auth_client.get(f'/documents/{doc.id}').get_data(as_text=True)


class TestExportAndRestore:
    def test_reminder_round_trips_into_another_account(
            self, auth_client, admin_user, sample_vehicle, test_user):
        db.session.add(Reminder(vehicle_id=sample_vehicle.id, user_id=test_user.id,
                                title='Licence due', reminder_type=KEY,
                                due_date=date(2031, 5, 20), recurrence='none',
                                notify_days_before=30))
        db.session.commit()

        data = json.loads(auth_client.get('/api/export/json').data)
        assert [r['reminder_type'] for r in data['vehicles'][0]['reminders']] == [KEY]

        restore_backup(data, admin_user)
        vehicle = Vehicle.query.filter_by(owner_id=admin_user.id).one()
        assert [r.reminder_type for r in vehicle.reminders] == [KEY]

    def test_document_type_is_exported(self, auth_client, sample_vehicle, test_user):
        db.session.add(Document(vehicle_id=sample_vehicle.id, user_id=test_user.id,
                                title='Licence scan', document_type=KEY,
                                filename='doc_licence.pdf',
                                original_filename='licence.pdf',
                                file_type='pdf', file_size=5))
        db.session.commit()
        data = json.loads(auth_client.get('/api/export/json').data)
        assert [d['document_type'] for d in data['vehicles'][0]['documents']] == [KEY]
