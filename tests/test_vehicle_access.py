"""A signed-in user must not reach a vehicle they have no access to."""
import io

import pytest

from app import db
from app.models import FuelLog, User, Vehicle

CSV = b'date,odometer,volume,total_cost\n2026-01-05,123456,40,99\n'
MAPPING = {
    'date_format': 'auto',
    'mapping_0': 'date',
    'mapping_1': 'odometer',
    'mapping_2': 'volume',
    'mapping_3': 'total_cost',
}


@pytest.fixture
def other_vehicle(app):
    """A vehicle of another user, shared with nobody."""
    owner = User(username='someoneelse', email='someoneelse@example.com')
    owner.set_password('TestPass123!')
    db.session.add(owner)
    db.session.commit()
    vehicle = Vehicle(owner_id=owner.id, name='Neighbour Van', vehicle_type='van',
                      fuel_type='diesel', odometer_unit='km')
    db.session.add(vehicle)
    db.session.commit()
    db.session.add(FuelLog(vehicle_id=vehicle.id, user_id=owner.id,
                           odometer=87654.0, volume=30.0, total_cost=50.0))
    db.session.commit()
    return vehicle


def _preview(client, vehicle_id):
    return client.post('/api/import/csv/preview', data={
        'data_type': 'fuel_logs',
        'vehicle_id': str(vehicle_id),
        'file': (io.BytesIO(CSV), 'fuel.csv'),
    }, content_type='multipart/form-data')


def _execute(client, vehicle_id):
    return client.post('/api/import/csv/execute', data={
        'data_type': 'fuel_logs', 'vehicle_id': str(vehicle_id), **MAPPING})


def _log_count(vehicle):
    return FuelLog.query.filter_by(vehicle_id=vehicle.id).count()


class TestCsvImportAccess:
    def test_preview_refuses_another_users_vehicle(self, auth_client, sample_vehicle,
                                                   other_vehicle):
        resp = _preview(auth_client, other_vehicle.id)

        assert resp.status_code == 302
        assert b'Neighbour Van' not in resp.data

    def test_execute_refuses_another_users_vehicle(self, auth_client, sample_vehicle,
                                                   other_vehicle):
        # The vehicle id travels in the form, so it can be swapped after a
        # preview of one's own vehicle.
        assert _preview(auth_client, sample_vehicle.id).status_code == 200

        resp = _execute(auth_client, other_vehicle.id)

        assert resp.status_code == 302
        assert _log_count(other_vehicle) == 1
        assert _log_count(sample_vehicle) == 0

    def test_shared_vehicle_can_still_be_imported_into(self, auth_client, test_user,
                                                       other_vehicle):
        test_user.shared_vehicles.append(other_vehicle)
        db.session.commit()

        assert _preview(auth_client, other_vehicle.id).status_code == 200
        _execute(auth_client, other_vehicle.id)

        assert _log_count(other_vehicle) == 2


class TestTripFormAccess:
    def test_new_trip_form_hides_another_users_odometer(self, auth_client, sample_vehicle,
                                                        other_vehicle):
        resp = auth_client.get(f'/trips/new?vehicle_id={other_vehicle.id}')

        assert resp.status_code == 200
        assert b'87654' not in resp.data

    def test_new_trip_form_shows_ones_own_odometer(self, auth_client, sample_fuel_log):
        resp = auth_client.get(f'/trips/new?vehicle_id={sample_fuel_log.vehicle_id}')

        assert str(sample_fuel_log.odometer).encode() in resp.data
