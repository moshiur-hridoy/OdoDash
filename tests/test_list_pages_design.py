"""The list pages rebuilt on the design system (trips, charging, reminders,
recurring, maintenance, documents, notes)."""
import re
from datetime import date, timedelta

from app import db
from app.models import Note, Reminder, Trip, Vehicle


def _text(resp):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', resp.get_data(as_text=True)))


class TestReminderBuckets:
    def test_completed_reminder_is_only_listed_as_completed(self, auth_client, test_user, sample_vehicle):
        db.session.add(Reminder(vehicle_id=sample_vehicle.id, user_id=test_user.id, title='Done one',
                                reminder_type='service', due_date=date.today() + timedelta(days=90),
                                recurrence='none', is_completed=True))
        db.session.commit()
        body = auth_client.get('/reminders/?completed=true').get_data(as_text=True)
        assert body.count('Done one') == 1
        assert 'aria-label="Later"' not in body

    def test_complete_returns_to_the_filtered_list(self, auth_client, test_user, sample_vehicle):
        reminder = Reminder(vehicle_id=sample_vehicle.id, user_id=test_user.id, title='Oil',
                            reminder_type='service', due_date=date.today(), recurrence='none')
        db.session.add(reminder)
        db.session.commit()
        resp = auth_client.post(f'/reminders/{reminder.id}/complete',
                                data={'next': '/reminders/?completed=true'})
        assert resp.status_code == 302
        assert resp.headers['Location'].endswith('/reminders/?completed=true')

    def test_complete_ignores_an_offsite_next(self, auth_client, test_user, sample_vehicle):
        reminder = Reminder(vehicle_id=sample_vehicle.id, user_id=test_user.id, title='Oil',
                            reminder_type='service', due_date=date.today(), recurrence='none')
        db.session.add(reminder)
        db.session.commit()
        resp = auth_client.post(f'/reminders/{reminder.id}/complete', data={'next': 'https://evil.example/'})
        assert 'evil.example' not in resp.headers['Location']


class TestTripsPage:
    def _trips(self, test_user, vehicle, count):
        for i in range(count):
            db.session.add(Trip(vehicle_id=vehicle.id, user_id=test_user.id, date=date(2026, 1, 1) + timedelta(days=i),
                                start_odometer=1000 + i * 10, end_odometer=1010 + i * 10,
                                purpose='business' if i % 2 else 'personal'))
        db.session.commit()

    def test_totals_cover_every_page(self, auth_client, test_user, sample_vehicle):
        self._trips(test_user, sample_vehicle, 60)
        body = auth_client.get('/trips/').get_data(as_text=True)
        text = _text(auth_client.get('/trips/'))
        assert 'Page 1 of 2' in text
        assert '600.0' in body   # 60 trips x 10
        assert '300.0' in body   # the 30 business ones

    def test_fuel_column_only_when_a_trip_has_gauge_readings(self, auth_client, test_user, sample_vehicle):
        self._trips(test_user, sample_vehicle, 1)
        assert '>Fuel</th>' not in auth_client.get('/trips/').get_data(as_text=True)
        Trip.query.first().start_fuel_level = 80
        db.session.commit()
        assert '>Fuel</th>' in auth_client.get('/trips/').get_data(as_text=True)

    def test_delete_returns_to_the_filtered_list(self, auth_client, test_user, sample_vehicle):
        self._trips(test_user, sample_vehicle, 1)
        trip = Trip.query.first()
        resp = auth_client.post(f'/trips/{trip.id}/delete', data={'next': '/trips/?purpose=personal'})
        assert resp.headers['Location'].endswith('/trips/?purpose=personal')


class TestNotesPage:
    def test_vehicle_filter(self, auth_client, test_user, sample_vehicle):
        other = Vehicle(owner_id=test_user.id, name='Second', vehicle_type='car')
        db.session.add(other)
        db.session.commit()
        db.session.add_all([
            Note(vehicle_id=sample_vehicle.id, user_id=test_user.id, date=date(2026, 3, 1), content='First car note'),
            Note(vehicle_id=other.id, user_id=test_user.id, date=date(2026, 3, 2), content='Second car note'),
        ])
        db.session.commit()
        body = auth_client.get(f'/notes/?vehicle={other.id}').get_data(as_text=True)
        assert 'Second car note' in body
        assert 'First car note' not in body

    def test_long_note_gets_a_details_toggle(self, auth_client, test_user, sample_vehicle):
        db.session.add(Note(vehicle_id=sample_vehicle.id, user_id=test_user.id, date=date(2026, 3, 1),
                            title='Rattle', content='Line one\nLine two'))
        db.session.commit()
        body = auth_client.get('/notes/').get_data(as_text=True)
        assert 'data-disclosure' in body
        assert 'class="exp-detail"' in body


class TestChargingPage:
    def test_charging_page_shares_the_fuel_tab_log(self, auth_client, test_user):
        ev = Vehicle(owner_id=test_user.id, name='Leaf', vehicle_type='car', fuel_type='electric')
        db.session.add(ev)
        db.session.commit()
        resp = auth_client.get('/charging/')
        assert resp.status_code == 200
        assert 'No charging sessions' in resp.get_data(as_text=True)
