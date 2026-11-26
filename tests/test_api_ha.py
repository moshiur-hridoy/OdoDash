"""Tests for the Home Assistant API endpoints."""
import pytest
from datetime import date, timedelta
from app import db as _db_ext
from app.models import User, Vehicle, FuelLog, Trip, MaintenanceSchedule, Reminder, ChargingSession


def make_ha_headers(api_key):
    return {'Authorization': f'Bearer {api_key}'}


@pytest.fixture
def ha_user(app):
    """A user with a generated API key for HA testing."""
    user = User(
        username='hauser',
        email='ha@example.com',
    )
    user.set_password('HaPass123!')
    _db_ext.session.add(user)
    _db_ext.session.commit()
    user.generate_api_key()
    _db_ext.session.commit()
    return user


@pytest.fixture
def ha_headers(ha_user):
    return make_ha_headers(ha_user.api_key)


@pytest.fixture
def ha_vehicle(ha_user):
    vehicle = Vehicle(
        owner_id=ha_user.id,
        name='HA Test Car',
        vehicle_type='car',
        make='Ford',
        model='Focus',
        year=2022,
        fuel_type='petrol',
    )
    _db_ext.session.add(vehicle)
    _db_ext.session.commit()
    return vehicle


@pytest.fixture
def ha_fuel_log(ha_user, ha_vehicle):
    log = FuelLog(
        vehicle_id=ha_vehicle.id,
        user_id=ha_user.id,
        date=date(2024, 1, 10),
        odometer=5000.0,
        volume=40.0,
        price_per_unit=1.60,
        total_cost=64.0,
        is_full_tank=True,
    )
    _db_ext.session.add(log)
    log2 = FuelLog(
        vehicle_id=ha_vehicle.id,
        user_id=ha_user.id,
        date=date(2024, 2, 10),
        odometer=5500.0,
        volume=38.0,
        price_per_unit=1.62,
        total_cost=61.56,
        is_full_tank=True,
    )
    _db_ext.session.add(log2)
    _db_ext.session.commit()
    return log


@pytest.fixture
def ha_trip(ha_user, ha_vehicle):
    trip = Trip(
        vehicle_id=ha_vehicle.id,
        user_id=ha_user.id,
        date=date(2024, 2, 1),
        start_odometer=5500.0,
        end_odometer=5510.0,
        purpose='business',
        description='Client meeting',
    )
    _db_ext.session.add(trip)
    _db_ext.session.commit()
    return trip


class TestHaAuth:
    def test_no_token_returns_401(self, client):
        resp = client.get('/api/ha/status')
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self, client):
        resp = client.get('/api/ha/status', headers={'Authorization': 'Bearer bad-token'})
        assert resp.status_code == 401

    def test_missing_bearer_scheme_returns_401(self, client, ha_user):
        resp = client.get('/api/ha/status', headers={'Authorization': ha_user.api_key})
        assert resp.status_code == 401

    def test_valid_token_returns_200(self, client, ha_headers):
        resp = client.get('/api/ha/status', headers=ha_headers)
        assert resp.status_code == 200


class TestHaStatus:
    def test_status_response(self, client, ha_headers, ha_user):
        resp = client.get('/api/ha/status', headers=ha_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'online'
        assert data['user'] == ha_user.username
        assert 'version' in data


class TestHaVehicles:
    def test_list_vehicles_empty(self, client, ha_headers):
        resp = client.get('/api/ha/vehicles', headers=ha_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'vehicles' in data
        assert data['count'] == 0

    def test_list_vehicles_with_vehicle(self, client, ha_headers, ha_vehicle):
        resp = client.get('/api/ha/vehicles', headers=ha_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['count'] == 1
        v = data['vehicles'][0]
        assert v['name'] == 'HA Test Car'
        assert 'current_odometer' in v
        assert 'fuel_type' in v
        assert v['unit_distance'] == 'km'
        assert v['unit_volume'] == 'L'
        assert v['currency'] == 'USD'

    def test_vehicle_detail(self, client, ha_headers, ha_vehicle):
        resp = client.get(f'/api/ha/vehicles/{ha_vehicle.id}', headers=ha_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['id'] == ha_vehicle.id
        assert data['name'] == 'HA Test Car'
        assert data['unit_distance'] == 'km'
        assert data['unit_volume'] == 'L'
        assert data['currency'] == 'USD'

    def test_vehicle_detail_not_found(self, client, ha_headers):
        resp = client.get('/api/ha/vehicles/99999', headers=ha_headers)
        assert resp.status_code == 404

    def test_vehicle_detail_other_user(self, client, ha_headers, sample_vehicle):
        """Cannot access another user's vehicle."""
        resp = client.get(f'/api/ha/vehicles/{sample_vehicle.id}', headers=ha_headers)
        assert resp.status_code == 404


class TestHaVehicleStats:
    def test_vehicle_stats_no_fuel_logs(self, client, ha_headers, ha_vehicle):
        resp = client.get(f'/api/ha/vehicles/{ha_vehicle.id}/stats', headers=ha_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['vehicle_id'] == ha_vehicle.id
        assert 'total_distance' in data
        assert 'avg_consumption' in data

    def test_vehicle_stats_with_fuel_logs(self, client, ha_headers, ha_vehicle, ha_fuel_log):
        resp = client.get(f'/api/ha/vehicles/{ha_vehicle.id}/stats', headers=ha_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['fill_count'] == 2
        assert data['total_fuel'] > 0
        assert data['distance_unit'] == 'km'
        assert data['volume_unit'] == 'L'
        assert data['currency'] == 'USD'

    def test_vehicle_stats_current_odometer_from_trip(self, client, ha_headers, ha_vehicle, ha_trip):
        resp = client.get(f'/api/ha/vehicles/{ha_vehicle.id}/stats', headers=ha_headers)
        assert resp.status_code == 200
        assert resp.get_json()['current_odometer'] == ha_trip.end_odometer

    def test_vehicle_stats_not_found(self, client, ha_headers):
        resp = client.get('/api/ha/vehicles/99999/stats', headers=ha_headers)
        assert resp.status_code == 404

    def test_vehicle_stats_with_days_param(self, client, ha_headers, ha_vehicle, ha_fuel_log):
        resp = client.get(f'/api/ha/vehicles/{ha_vehicle.id}/stats?days=365', headers=ha_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['period_days'] == 365


class TestHaAlerts:
    @pytest.fixture
    def due_maintenance(self, ha_user, ha_vehicle):
        schedule = MaintenanceSchedule(
            vehicle_id=ha_vehicle.id,
            user_id=ha_user.id,
            name='Oil Change',
            maintenance_type='oil_change',
            next_due_date=date.today() - timedelta(days=1),
            is_active=True,
        )
        _db_ext.session.add(schedule)
        _db_ext.session.commit()
        return schedule

    @pytest.fixture
    def overdue_reminder(self, ha_user, ha_vehicle):
        reminder = Reminder(
            vehicle_id=ha_vehicle.id,
            user_id=ha_user.id,
            title='MOT',
            reminder_type='mot',
            due_date=date.today() - timedelta(days=2),
            notify_days_before=7,
            is_completed=False,
        )
        _db_ext.session.add(reminder)
        _db_ext.session.commit()
        return reminder

    def test_alerts_no_issues(self, client, ha_headers):
        resp = client.get('/api/ha/alerts', headers=ha_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'alerts' in data
        assert 'count' in data
        assert 'has_alerts' in data
        assert data['count'] == 0
        assert data['has_alerts'] is False

    def test_alerts_requires_auth(self, client):
        resp = client.get('/api/ha/alerts')
        assert resp.status_code == 401

    def test_alerts_include_maintenance_and_reminder(self, client, ha_headers, due_maintenance, overdue_reminder):
        resp = client.get('/api/ha/alerts', headers=ha_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['count'] == 2
        statuses = {(item['type'], item['status']) for item in data['alerts']}
        assert ('maintenance', 'overdue') in statuses
        assert ('reminder', 'overdue') in statuses


class TestHaSummary:
    def test_summary_no_vehicles(self, client, ha_headers):
        resp = client.get('/api/ha/summary', headers=ha_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'total_vehicles' in data
        assert 'total_fuel_cost' in data
        assert 'alerts_count' in data
        assert data['total_vehicles'] == 0

    def test_summary_with_vehicle(self, client, ha_headers, ha_vehicle, ha_fuel_log):
        resp = client.get('/api/ha/summary', headers=ha_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['total_vehicles'] == 1


class TestHaAddFuel:
    def test_add_fuel_success(self, client, ha_headers, ha_vehicle):
        resp = client.post(
            '/api/ha/fuel/add',
            json={
                'vehicle_id': ha_vehicle.id,
                'date': '2024-03-01',
                'odometer': 6000.0,
                'volume': 42.0,
                'price_per_unit': 1.65,
                'total_cost': 69.30,
            },
            headers=ha_headers,
            content_type='application/json'
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['success'] is True
        assert 'id' in data
        log = _db_ext.session.get(FuelLog, data['id'])
        assert log is not None
        assert log.user_id == ha_vehicle.owner_id

    def test_add_fuel_missing_required_field(self, client, ha_headers, ha_vehicle):
        resp = client.post(
            '/api/ha/fuel/add',
            json={
                'vehicle_id': ha_vehicle.id,
                'date': '2024-03-01',
                # missing odometer and other required fields
            },
            headers=ha_headers,
            content_type='application/json'
        )
        assert resp.status_code == 400

    def test_add_fuel_no_body(self, client, ha_headers):
        # Flask returns 415 when no Content-Type is set, 400 when JSON body is empty
        resp = client.post('/api/ha/fuel/add', headers=ha_headers)
        assert resp.status_code in (400, 415)

    def test_add_fuel_vehicle_not_found(self, client, ha_headers):
        resp = client.post(
            '/api/ha/fuel/add',
            json={
                'vehicle_id': 99999,
                'date': '2024-03-01',
                'odometer': 6000.0,
                'volume': 42.0,
                'price_per_unit': 1.65,
                'total_cost': 69.30,
            },
            headers=ha_headers,
            content_type='application/json'
        )
        assert resp.status_code == 404

    def test_add_fuel_other_users_vehicle(self, client, ha_headers, sample_vehicle):
        """Cannot add fuel to another user's vehicle."""
        resp = client.post(
            '/api/ha/fuel/add',
            json={
                'vehicle_id': sample_vehicle.id,
                'date': '2024-03-01',
                'odometer': 6000.0,
                'volume': 42.0,
                'price_per_unit': 1.65,
                'total_cost': 69.30,
            },
            headers=ha_headers,
            content_type='application/json'
        )
        assert resp.status_code == 404

    def test_add_fuel_no_auth(self, client, ha_vehicle):
        resp = client.post(
            '/api/ha/fuel/add',
            json={
                'vehicle_id': ha_vehicle.id,
                'date': '2024-03-01',
                'odometer': 6000.0,
                'volume': 42.0,
                'price_per_unit': 1.65,
                'total_cost': 69.30,
            },
            content_type='application/json'
        )
        assert resp.status_code == 401


class TestHaSharingAndUnits:
    """Shared vehicles, alert vehicle ids and per-vehicle consumption units."""

    def _other_vehicle(self, **kwargs):
        owner = User(username='haowner', email='haowner@example.com')
        owner.set_password('OwnerPass123!')
        _db_ext.session.add(owner)
        _db_ext.session.commit()
        vehicle = Vehicle(owner_id=owner.id, name='Family Car', vehicle_type='car',
                          make='Toyota', model='Corolla', year=2020,
                          fuel_type='petrol', **kwargs)
        _db_ext.session.add(vehicle)
        _db_ext.session.commit()
        return vehicle

    def test_shared_vehicle_is_listed_and_readable(self, client, ha_user, ha_headers):
        vehicle = self._other_vehicle()
        ha_user.shared_vehicles.append(vehicle)
        _db_ext.session.commit()

        ids = [v['id'] for v in client.get('/api/ha/vehicles', headers=ha_headers).get_json()['vehicles']]
        assert vehicle.id in ids
        assert client.get(f'/api/ha/vehicles/{vehicle.id}/stats', headers=ha_headers).status_code == 200

    def test_unshared_vehicle_stays_hidden(self, client, ha_headers):
        vehicle = self._other_vehicle()
        ids = [v['id'] for v in client.get('/api/ha/vehicles', headers=ha_headers).get_json()['vehicles']]
        assert vehicle.id not in ids
        assert client.get(f'/api/ha/vehicles/{vehicle.id}', headers=ha_headers).status_code == 404

    def test_alerts_carry_vehicle_id(self, client, ha_user, ha_headers, ha_vehicle):
        _db_ext.session.add(Reminder(
            vehicle_id=ha_vehicle.id, user_id=ha_user.id, title='Insurance', reminder_type='insurance',
            due_date=date.today() - timedelta(days=1),
        ))
        _db_ext.session.commit()
        alerts = client.get('/api/ha/alerts', headers=ha_headers).get_json()['alerts']
        assert alerts
        assert all(a['vehicle_id'] == ha_vehicle.id for a in alerts)

    def test_consumption_unit_follows_vehicle_odometer_unit(self, client, ha_user, ha_headers, ha_vehicle, ha_fuel_log):
        ha_user.distance_unit = 'km'
        ha_vehicle.odometer_unit = 'mi'
        _db_ext.session.commit()
        data = client.get(f'/api/ha/vehicles/{ha_vehicle.id}/stats', headers=ha_headers).get_json()
        assert data['consumption_unit'] == 'mpg'
        assert data['distance_unit'] == 'mi'

    def test_hours_vehicle_has_no_consumption(self, client, ha_headers, ha_vehicle, ha_fuel_log):
        ha_vehicle.tracking_unit = 'hours'
        _db_ext.session.commit()
        data = client.get(f'/api/ha/vehicles/{ha_vehicle.id}/stats', headers=ha_headers).get_json()
        assert data['avg_consumption'] is None
        assert data['consumption_unit'] is None
        assert data['distance_unit'] == 'h'


class TestHaOverview:
    """GET /api/ha/overview: one request with everything the integration needs."""

    def test_requires_token(self, client):
        assert client.get('/api/ha/overview').status_code == 401

    def test_empty_account(self, client, ha_headers, ha_user):
        data = client.get('/api/ha/overview', headers=ha_headers).get_json()
        assert data['user'] == ha_user.username
        assert data['vehicles'] == []
        assert data['alerts_count'] == 0
        assert 'version' in data and 'currency' in data

    def test_current_odometer_from_trip(self, client, ha_headers, ha_vehicle, ha_trip):
        data = client.get('/api/ha/overview', headers=ha_headers).get_json()
        vehicle = next(v for v in data['vehicles'] if v['id'] == ha_vehicle.id)
        assert vehicle['current_odometer'] == ha_trip.end_odometer

    def test_other_users_vehicles_hidden(self, client, ha_headers, sample_vehicle):
        data = client.get('/api/ha/overview', headers=ha_headers).get_json()
        assert sample_vehicle.id not in [v['id'] for v in data['vehicles']]

    def test_three_fills(self, client, ha_user, ha_headers, ha_vehicle):
        today = date.today()
        for i, (odo, vol, cost) in enumerate([(1000, 40.0, 60.0), (1500, 30.0, 48.0), (2000, 35.0, 56.0)]):
            _db_ext.session.add(FuelLog(
                vehicle_id=ha_vehicle.id, user_id=ha_user.id,
                date=today - timedelta(days=60 - i * 25),
                odometer=float(odo), volume=vol, price_per_unit=1.5,
                total_cost=cost, is_full_tank=True,
            ))
        _db_ext.session.commit()

        data = client.get('/api/ha/overview', headers=ha_headers).get_json()
        assert len(data['vehicles']) == 1
        v = data['vehicles'][0]
        assert v['id'] == ha_vehicle.id
        assert v['is_electric'] is False
        assert v['current_odometer'] == 2000.0
        # (30 + 35) litres over 1000 km, first fill skipped
        assert v['avg_consumption'] == 6.5
        assert v['consumption_unit'] == 'L/100km'
        assert v['total_fuel_cost'] == 164.0
        assert v['total_expenses'] == 0
        assert v['total_cost'] == 164.0
        # fills 60, 35 and 10 days ago: only the last two are inside 30 days
        assert v['cost_last_30_days'] == 56.0
        assert v['last_fill_date'] == (today - timedelta(days=10)).isoformat()
        assert v['last_fill_volume'] == 35.0
        assert v['last_fill_cost'] == 56.0
        assert v['last_charge'] is None
        # the same numbers as the per-vehicle stats endpoint
        stats = client.get(f'/api/ha/vehicles/{ha_vehicle.id}/stats', headers=ha_headers).get_json()
        assert v['avg_consumption'] == stats['avg_consumption']
        assert v['total_cost'] == stats['total_cost']

    def test_ev_last_charge(self, client, ha_user, ha_headers):
        ev = Vehicle(owner_id=ha_user.id, name='EV', vehicle_type='car',
                     make='Tesla', model='Model 3', year=2023, fuel_type='electric')
        _db_ext.session.add(ev)
        _db_ext.session.commit()
        for d, kwh, soc in [(date(2024, 3, 1), 20.0, 70), (date(2024, 3, 5), 30.0, 80)]:
            _db_ext.session.add(ChargingSession(
                vehicle_id=ev.id, user_id=ha_user.id, date=d,
                kwh_added=kwh, start_soc=20, end_soc=soc,
            ))
        _db_ext.session.commit()

        v = client.get('/api/ha/overview', headers=ha_headers).get_json()['vehicles'][0]
        assert v['is_electric'] is True
        assert v['last_charge']['date'] == '2024-03-05'
        assert v['last_charge']['kwh_added'] == 30.0
        assert v['last_charge']['end_soc'] == 80

    def test_hours_vehicle_has_null_consumption(self, client, ha_headers, ha_vehicle, ha_fuel_log):
        ha_vehicle.tracking_unit = 'hours'
        _db_ext.session.commit()
        v = client.get('/api/ha/overview', headers=ha_headers).get_json()['vehicles'][0]
        assert v['avg_consumption'] is None
        assert v['consumption_unit'] is None
        assert v['distance_unit'] == 'h'

    def test_alerts_grouped_per_vehicle(self, client, ha_user, ha_headers, ha_vehicle):
        _db_ext.session.add(Reminder(
            vehicle_id=ha_vehicle.id, user_id=ha_user.id, title='MOT', reminder_type='mot',
            due_date=date.today() - timedelta(days=1),
        ))
        _db_ext.session.commit()
        data = client.get('/api/ha/overview', headers=ha_headers).get_json()
        assert data['alerts_count'] == 1
        alerts = data['vehicles'][0]['alerts']
        assert len(alerts) == 1
        assert alerts[0]['type'] == 'reminder'
        assert alerts[0]['vehicle_id'] == ha_vehicle.id


class TestHaToken:
    """The scoped Home Assistant key (odoha_) works on /api/ha/* only."""

    @pytest.fixture
    def ha_token_headers(self, ha_user):
        token = ha_user.generate_ha_token()
        _db_ext.session.commit()
        return make_ha_headers(token)

    def test_generated_token_shape(self, ha_user):
        token = ha_user.generate_ha_token()
        assert token.startswith('odoha_')
        assert len(token) <= User.__table__.c.ha_token.type.length
        assert ha_user.ha_token_created_at is not None

    def test_works_on_ha_api(self, client, ha_user, ha_token_headers):
        resp = client.get('/api/ha/status', headers=ha_token_headers)
        assert resp.status_code == 200
        assert resp.get_json()['user'] == ha_user.username
        assert client.get('/api/ha/overview', headers=ha_token_headers).status_code == 200

    def test_old_api_key_still_works(self, client, ha_headers):
        assert client.get('/api/ha/status', headers=ha_headers).status_code == 200

    def test_rejected_by_v1_api(self, client, ha_token_headers):
        assert client.get('/api/v1/vehicles', headers=ha_token_headers).status_code == 401
        token = ha_token_headers['Authorization'].split(' ', 1)[1]
        assert client.get('/api/v1/vehicles', headers={'X-API-Key': token}).status_code == 401

    def test_rejected_by_calendar(self, client, ha_user):
        token = ha_user.generate_ha_token()
        _db_ext.session.commit()
        assert client.get(f'/api/calendar/feed.ics?token={token}').status_code == 401

    def test_revoked_token_rejected(self, client, ha_user, ha_token_headers):
        ha_user.revoke_ha_token()
        _db_ext.session.commit()
        assert client.get('/api/ha/status', headers=ha_token_headers).status_code == 401

    def test_can_add_fuel(self, client, ha_token_headers, ha_vehicle):
        resp = client.post('/api/ha/fuel/add', headers=ha_token_headers, json={
            'vehicle_id': ha_vehicle.id, 'date': '2024-05-01', 'odometer': 6000,
            'volume': 30, 'price_per_unit': 1.5, 'total_cost': 45,
        })
        assert resp.status_code == 201

    def test_viewer_cannot_add_fuel(self, client, ha_user, ha_token_headers, ha_vehicle):
        ha_user.role = 'viewer'
        _db_ext.session.commit()
        resp = client.post('/api/ha/fuel/add', headers=ha_token_headers, json={
            'vehicle_id': ha_vehicle.id, 'date': '2024-05-01', 'odometer': 6000,
            'volume': 30, 'price_per_unit': 1.5, 'total_cost': 45,
        })
        assert resp.status_code == 403
        assert FuelLog.query.filter_by(odometer=6000.0).count() == 0

    def test_generate_and_revoke_routes(self, auth_client, test_user):
        resp = auth_client.post('/api/key/ha/generate')
        assert resp.status_code == 200
        token = resp.get_json()['ha_token']
        assert token.startswith('odoha_')
        assert test_user.ha_token == token
        # the account API key is untouched
        assert test_user.api_key is None
        assert auth_client.post('/api/key/ha/revoke').status_code == 200
        assert test_user.ha_token is None

    def test_viewer_can_manage_own_ha_token(self, auth_client, test_user):
        test_user.role = 'viewer'
        _db_ext.session.commit()
        assert auth_client.post('/api/key/ha/generate').status_code == 200

    def test_generate_requires_login(self, client):
        assert client.post('/api/key/ha/generate').status_code in (302, 401)
