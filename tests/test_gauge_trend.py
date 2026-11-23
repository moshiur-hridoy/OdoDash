"""The vehicle page's gauges are coloured by the latest spans against the lifetime average."""

from datetime import date, timedelta

from app import db
from app.models import ChargingSession, FuelLog, Vehicle
from app.utils import consumption_trend


def _fill_ups(vehicle, user, litres_per_span, km_per_span=500.0):
    """One full tank per span, so each entry in ``litres_per_span`` is a span."""
    odometer = 10000.0
    day = date(2026, 1, 1)
    db.session.add(FuelLog(vehicle_id=vehicle.id, user_id=user.id, date=day, odometer=odometer,
                           volume=30.0, price_per_unit=1.5, total_cost=45.0, is_full_tank=True))
    for litres in litres_per_span:
        odometer += km_per_span
        day += timedelta(days=10)
        db.session.add(FuelLog(vehicle_id=vehicle.id, user_id=user.id, date=day, odometer=odometer,
                               volume=litres, price_per_unit=1.5, total_cost=litres * 1.5,
                               is_full_tank=True))
    db.session.commit()


def _charges(vehicle, user, kwh_per_span, km_per_span=100.0):
    odometer = 5000.0
    day = date(2026, 1, 1)
    db.session.add(ChargingSession(vehicle_id=vehicle.id, user_id=user.id, date=day,
                                   odometer=odometer, kwh_added=10.0))
    for kwh in kwh_per_span:
        odometer += km_per_span
        day += timedelta(days=5)
        db.session.add(ChargingSession(vehicle_id=vehicle.id, user_id=user.id, date=day,
                                       odometer=odometer, kwh_added=kwh))
    db.session.commit()


class TestConsumptionTrend:
    def test_lower_is_better(self):
        assert consumption_trend(9.0, 10.0, True) == 'better'
        assert consumption_trend(11.0, 10.0, True) == 'worse'

    def test_higher_is_better(self):
        assert consumption_trend(55.0, 50.0, False) == 'better'
        assert consumption_trend(45.0, 50.0, False) == 'worse'

    def test_inside_the_margin_is_unmarked(self):
        assert consumption_trend(10.3, 10.0, True) is None

    def test_missing_figures_are_unmarked(self):
        assert consumption_trend(None, 10.0, True) is None
        assert consumption_trend(10.0, 0, True) is None


class TestRecentFuelConsumption:
    def test_needs_more_spans_than_the_window(self, app, test_user, sample_vehicle):
        _fill_ups(sample_vehicle, test_user, [40.0, 40.0, 40.0])  # three spans, window is three
        assert sample_vehicle.get_recent_consumption('L/100km', 'L') is None

    def test_recent_spans_against_the_average(self, app, test_user, sample_vehicle):
        # 8 L/100km for two spans, then three at 10 L/100km.
        _fill_ups(sample_vehicle, test_user, [40.0, 40.0, 50.0, 50.0, 50.0])
        recent, average = sample_vehicle.get_recent_consumption('L/100km', 'L')
        assert abs(recent - 10.0) < 0.001
        assert abs(average - 9.2) < 0.001
        assert average == sample_vehicle.get_average_consumption('L/100km', 'L')

    def test_by_fuel_entry_carries_the_pair(self, app, test_user, sample_vehicle):
        _fill_ups(sample_vehicle, test_user, [40.0, 40.0, 50.0, 50.0, 50.0])
        entry = sample_vehicle.get_average_consumption_by_fuel('L/100km', 'L')[0]
        assert entry['recent'] is not None


class TestRecentChargingConsumption:
    def test_needs_more_spans_than_the_window(self, app, test_user):
        ev = _ev(test_user)
        _charges(ev, test_user, [15.0, 15.0, 15.0])
        assert ev.get_recent_charging_consumption() is None

    def test_recent_charges_against_lifetime(self, app, test_user):
        ev = _ev(test_user)
        # 15 kWh / 100 km for two spans, then three at 20 kWh / 100 km.
        _charges(ev, test_user, [15.0, 15.0, 20.0, 20.0, 20.0])
        recent, lifetime = ev.get_recent_charging_consumption()
        assert abs(recent - 20.0) < 0.001
        assert abs(lifetime - 18.0) < 0.001


def _ev(user):
    ev = Vehicle(owner_id=user.id, name='Leaf', vehicle_type='car', fuel_type='electric',
                 odometer_unit='km')
    db.session.add(ev)
    db.session.commit()
    return ev


class TestGaugeColour:
    def _page(self, auth_client, vehicle):
        return auth_client.get(f'/vehicles/{vehicle.id}').get_data(as_text=True)

    def test_better_is_green(self, auth_client, test_user, sample_vehicle):
        test_user.consumption_unit = 'L/100km'
        db.session.commit()
        # Last three spans use less fuel than the earlier ones.
        _fill_ups(sample_vehicle, test_user, [50.0, 50.0, 40.0, 40.0, 40.0])
        html = self._page(auth_client, sample_vehicle)
        assert 'class="vp-gauge__fill vp-gauge__fill--better"' in html
        assert 'better than your average' in html

    def test_worse_is_red(self, auth_client, test_user, sample_vehicle):
        test_user.consumption_unit = 'L/100km'
        db.session.commit()
        _fill_ups(sample_vehicle, test_user, [40.0, 40.0, 50.0, 50.0, 50.0])
        html = self._page(auth_client, sample_vehicle)
        assert 'class="vp-gauge__fill vp-gauge__fill--worse"' in html
        assert 'worse than your average' in html

    def test_in_line_is_yellow(self, auth_client, test_user, sample_vehicle):
        test_user.consumption_unit = 'L/100km'
        db.session.commit()
        _fill_ups(sample_vehicle, test_user, [40.0, 40.0, 41.0, 41.0, 41.0])
        html = self._page(auth_client, sample_vehicle)
        assert 'class="vp-gauge__fill vp-gauge__fill--steady"' in html
        assert 'In line with your average' in html

    def test_higher_is_better_units_flip_the_direction(self, auth_client, test_user, sample_vehicle):
        test_user.consumption_unit = 'km/L'
        db.session.commit()
        # Fewer litres per span means more km/L: the recent spans are better.
        _fill_ups(sample_vehicle, test_user, [50.0, 50.0, 40.0, 40.0, 40.0])
        html = self._page(auth_client, sample_vehicle)
        assert 'class="vp-gauge__fill vp-gauge__fill--better"' in html

    def test_km_per_litre_gauge_arc_is_drawn(self, auth_client, test_user, sample_vehicle):
        test_user.consumption_unit = 'km/L'
        db.session.commit()
        _fill_ups(sample_vehicle, test_user, [40.0, 40.0])
        html = self._page(auth_client, sample_vehicle)
        assert 'class="vp-gauge__fill' in html

    def test_few_fill_ups_keep_the_plain_gauge(self, auth_client, test_user, sample_vehicle):
        test_user.consumption_unit = 'L/100km'
        db.session.commit()
        _fill_ups(sample_vehicle, test_user, [40.0, 40.0])
        html = self._page(auth_client, sample_vehicle)
        assert 'class="vp-gauge__fill vp-gauge__fill--' not in html
        assert 'your average' not in html

    def test_charging_gauge_is_coloured(self, auth_client, test_user):
        ev = _ev(test_user)
        _charges(ev, test_user, [15.0, 15.0, 20.0, 20.0, 20.0])
        html = self._page(auth_client, ev)
        assert 'class="vp-gauge__fill vp-gauge__fill--worse"' in html
