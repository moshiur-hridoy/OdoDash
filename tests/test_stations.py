import pytest
from app import db
from app.models import FuelStation, FuelLog, FuelPriceHistory, User, Vehicle
from datetime import date


@pytest.fixture
def sample_station(app, test_user):
    station = FuelStation(
        user_id=test_user.id,
        name='Shell Station',
        brand='Shell',
        address='123 Main St',
        city='London',
        postcode='SW1A 1AA',
    )
    db.session.add(station)
    db.session.commit()
    return station


@pytest.fixture
def station_with_prices(app, test_user, sample_station):
    price = FuelPriceHistory(
        station_id=sample_station.id,
        user_id=test_user.id,
        date=date(2024, 3, 1),
        fuel_type='petrol',
        price_per_unit=1.60,
    )
    db.session.add(price)
    db.session.commit()
    return sample_station


class TestStationIndex:
    def test_index_requires_auth(self, client):
        resp = client.get('/stations/', follow_redirects=False)
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']

    def test_index_returns_200(self, auth_client):
        resp = auth_client.get('/stations/')
        assert resp.status_code == 200

    def test_index_shows_stations(self, auth_client, sample_station):
        resp = auth_client.get('/stations/')
        assert resp.status_code == 200
        assert b'Shell Station' in resp.data


class TestStationNew:
    def test_new_requires_auth(self, client):
        resp = client.get('/stations/new', follow_redirects=False)
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']

    def test_get_new_form_returns_200(self, auth_client):
        resp = auth_client.get('/stations/new')
        assert resp.status_code == 200

    def test_create_station(self, auth_client, test_user):
        resp = auth_client.post('/stations/new', data={
            'name': 'BP Station',
            'brand': 'BP',
            'address': '456 High St',
            'city': 'Manchester',
            'postcode': 'M1 1AA',
        }, follow_redirects=True)
        assert resp.status_code == 200
        station = FuelStation.query.filter_by(name='BP Station').first()
        assert station is not None
        assert station.brand == 'BP'


class TestStationEdit:
    def test_edit_requires_auth(self, client, sample_station):
        resp = client.get(f'/stations/{sample_station.id}/edit', follow_redirects=False)
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']

    def test_get_edit_form_returns_200(self, auth_client, sample_station):
        resp = auth_client.get(f'/stations/{sample_station.id}/edit')
        assert resp.status_code == 200

    def test_edit_station(self, auth_client, sample_station):
        resp = auth_client.post(f'/stations/{sample_station.id}/edit', data={
            'name': 'Shell Garage',
            'brand': 'Shell',
            'address': '123 Main St',
            'city': 'London',
            'postcode': 'SW1A 1AA',
        }, follow_redirects=True)
        assert resp.status_code == 200
        db.session.refresh(sample_station)
        assert sample_station.name == 'Shell Garage'


def _add_fuel_log(vehicle, user, station_text):
    log = FuelLog(
        vehicle_id=vehicle.id,
        user_id=user.id,
        date=date(2024, 3, 1),
        odometer=10000,
        station=station_text,
    )
    db.session.add(log)
    db.session.commit()
    return log


class TestStationEditUpdatesLogs:
    """#37: a rename or rebrand updates the station text stored on fuel logs."""

    def _edit(self, auth_client, station, **form):
        return auth_client.post(
            f'/stations/{station.id}/edit', data=form, follow_redirects=True)

    def test_rename_updates_matching_logs(
            self, auth_client, test_user, sample_vehicle, sample_station):
        matching = _add_fuel_log(sample_vehicle, test_user, 'Shell Station (Shell)')
        by_name_only = _add_fuel_log(sample_vehicle, test_user, 'Shell Station')
        other_text = _add_fuel_log(sample_vehicle, test_user, 'Corner shop')

        resp = self._edit(auth_client, sample_station,
                          name='Shell Garage', brand='Shell')
        assert resp.status_code == 200

        db.session.refresh(matching)
        db.session.refresh(by_name_only)
        db.session.refresh(other_text)
        assert matching.station == 'Shell Garage (Shell)'
        assert by_name_only.station == 'Shell Station'
        assert other_text.station == 'Corner shop'

    def test_brand_only_change_updates_logs(
            self, auth_client, test_user, sample_vehicle, sample_station):
        log = _add_fuel_log(sample_vehicle, test_user, 'Shell Station (Shell)')

        resp = self._edit(auth_client, sample_station,
                          name='Shell Station', brand='Esso')
        assert resp.status_code == 200

        db.session.refresh(log)
        assert log.station == 'Shell Station (Esso)'

    def test_station_without_brand(
            self, auth_client, test_user, sample_vehicle):
        station = FuelStation(user_id=test_user.id, name='Village Pump')
        db.session.add(station)
        db.session.commit()
        log = _add_fuel_log(sample_vehicle, test_user, 'Village Pump')

        resp = self._edit(auth_client, station, name='Village Garage', brand='')
        assert resp.status_code == 200

        db.session.refresh(log)
        assert log.station == 'Village Garage'

    def test_same_display_text_leaves_logs(
            self, auth_client, test_user, sample_vehicle, sample_station):
        log = _add_fuel_log(sample_vehicle, test_user, 'Shell Station (Shell)')

        resp = self._edit(auth_client, sample_station,
                          name='Shell Station', brand='Shell',
                          address='9 New Road')
        assert resp.status_code == 200

        db.session.refresh(log)
        assert log.station == 'Shell Station (Shell)'

    def test_rename_leaves_logs_on_inaccessible_vehicles(
            self, auth_client, test_user, sample_vehicle, sample_station):
        other_user = User(username='otheruser', email='other@example.com')
        other_user.set_password('OtherPass123!')
        db.session.add(other_user)
        db.session.commit()
        other_vehicle = Vehicle(
            owner_id=other_user.id,
            name='Other Car',
            vehicle_type='car',
            make='Toyota',
            model='Corolla',
            fuel_type='petrol',
        )
        db.session.add(other_vehicle)
        db.session.commit()
        visible = _add_fuel_log(sample_vehicle, test_user, 'Shell Station (Shell)')
        hidden = _add_fuel_log(other_vehicle, other_user, 'Shell Station (Shell)')

        resp = self._edit(auth_client, sample_station,
                          name='Shell Garage', brand='Shell')
        assert resp.status_code == 200

        db.session.refresh(visible)
        db.session.refresh(hidden)
        assert visible.station == 'Shell Garage (Shell)'
        assert hidden.station == 'Shell Station (Shell)'


class TestStationDelete:
    def test_delete_requires_auth(self, client, sample_station):
        resp = client.post(f'/stations/{sample_station.id}/delete', follow_redirects=False)
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']

    def test_delete_station(self, auth_client, sample_station):
        station_id = sample_station.id
        resp = auth_client.post(f'/stations/{station_id}/delete', follow_redirects=True)
        assert resp.status_code == 200
        assert db.session.get(FuelStation, station_id) is None

    def test_delete_station_with_price_history(self, auth_client, test_user, sample_station):
        # #256 — deleting a station with price rows must cascade rather than
        # 500 on the NOT NULL station_id constraint.
        from datetime import date
        from app.models import FuelPriceHistory
        entry = FuelPriceHistory(
            station_id=sample_station.id,
            user_id=test_user.id,
            date=date(2026, 6, 9),
            fuel_type='petrol',
            price_per_unit=1.899,
        )
        db.session.add(entry)
        db.session.commit()
        station_id = sample_station.id
        resp = auth_client.post(f'/stations/{station_id}/delete', follow_redirects=True)
        assert resp.status_code == 200
        assert db.session.get(FuelStation, station_id) is None
        assert FuelPriceHistory.query.filter_by(station_id=station_id).count() == 0


class TestStationToggleFavorite:
    def test_toggle_requires_auth(self, client, sample_station):
        resp = client.post(f'/stations/{sample_station.id}/favorite', follow_redirects=False)
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']

    def test_toggle_favorite(self, auth_client, sample_station):
        assert sample_station.is_favorite is False
        resp = auth_client.post(f'/stations/{sample_station.id}/favorite')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert data['is_favorite'] is True

    def test_toggle_favorite_twice(self, auth_client, sample_station):
        auth_client.post(f'/stations/{sample_station.id}/favorite')
        resp = auth_client.post(f'/stations/{sample_station.id}/favorite')
        data = resp.get_json()
        assert data['is_favorite'] is False


class TestStationPriceHistory:
    def test_price_history_requires_auth(self, client, sample_station):
        resp = client.get(f'/stations/{sample_station.id}/prices', follow_redirects=False)
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']

    def test_price_history_returns_200(self, auth_client, station_with_prices):
        resp = auth_client.get(f'/stations/{station_with_prices.id}/prices')
        assert resp.status_code == 200

    def test_price_history_empty_station(self, auth_client, sample_station):
        resp = auth_client.get(f'/stations/{sample_station.id}/prices')
        assert resp.status_code == 200


class TestStationCheapest:
    def test_cheapest_requires_auth(self, client):
        resp = client.get('/stations/cheapest', follow_redirects=False)
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']

    def test_cheapest_returns_200(self, auth_client):
        resp = auth_client.get('/stations/cheapest')
        assert resp.status_code == 200

    def test_cheapest_with_prices(self, auth_client, station_with_prices):
        resp = auth_client.get('/stations/cheapest')
        assert resp.status_code == 200


class TestStationDeletePrice:
    def test_delete_price_requires_auth(self, client, station_with_prices):
        price = FuelPriceHistory.query.filter_by(station_id=station_with_prices.id).first()
        resp = client.post(f'/stations/prices/{price.id}/delete', follow_redirects=False)
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']

    def test_delete_price_removes_entry(self, auth_client, station_with_prices):
        price = FuelPriceHistory.query.filter_by(station_id=station_with_prices.id).first()
        price_id = price.id
        resp = auth_client.post(f'/stations/prices/{price_id}/delete', follow_redirects=True)
        assert resp.status_code == 200
        assert db.session.get(FuelPriceHistory, price_id) is None

    def test_delete_price_other_user_blocked(self, auth_client, sample_station):
        from app.models import User
        other = User(username='other', email='other@example.com')
        other.set_password('pw')
        db.session.add(other)
        db.session.commit()
        price = FuelPriceHistory(
            station_id=sample_station.id,
            user_id=other.id,
            date=date(2024, 4, 1),
            fuel_type='petrol',
            price_per_unit=1.55,
        )
        db.session.add(price)
        db.session.commit()
        price_id = price.id
        resp = auth_client.post(f'/stations/prices/{price_id}/delete', follow_redirects=True)
        assert resp.status_code == 200
        assert db.session.get(FuelPriceHistory, price_id) is not None
