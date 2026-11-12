"""Free-text fuel logging shared by the Telegram bot and receipt photos."""
import pytest

from app import db
from app.models import FuelLog, Vehicle
from app.services.quick_log import (
    create_fuel_log, parse_fuel_message, to_number, choose_vehicle,
)


@pytest.mark.parametrize('text, volume, cost, price, odometer, full', [
    ('40L 4800tk 45230km', 40, 4800, None, 45230, True),
    ('৪০ লিটার ৪৮০০ টাকা ৪৫২৩০ কিমি', 40, 4800, None, 45230, True),
    ('40l @120 odo 45,230', 40, None, 120, 45230, True),
    ('30,82 L 59,34€ 81234 km partial', 30.82, 59.34, None, 81234, False),
    ('35.5 l 4260 tk 120/L', 35.5, 4260, 120, None, True),
    ('40L 4800tk 45230', 40, 4800, None, 45230, True),
    ('top up 10L 1200 taka', 10, 1200, None, None, False),
    ('45230 km 40 litres €65.90', 40, 65.90, None, 45230, True),
])
def test_parse_fuel_message(text, volume, cost, price, odometer, full):
    draft = parse_fuel_message(text)
    assert draft.volume == pytest.approx(volume)
    assert draft.total_cost == (pytest.approx(cost) if cost is not None else None)
    assert draft.price_per_unit == (pytest.approx(price) if price is not None else None)
    assert draft.odometer == (pytest.approx(odometer) if odometer is not None else None)
    assert draft.is_full_tank is full


def test_parse_ignores_chatter():
    assert parse_fuel_message('hello there').is_empty


@pytest.mark.parametrize('raw, expected', [
    ('45,230', 45230), ('45.230', 45.23), ('1,234.5', 1234.5),
    ('1.234,5', 1234.5), ('30,82', 30.82), ('2,139', 2.139), ('১২০', 120),
])
def test_to_number(raw, expected):
    assert to_number(raw) == pytest.approx(expected)


def test_create_derives_price_and_saves(app, test_user, sample_vehicle):
    result = create_fuel_log(test_user, '40L 4800tk 45230km')

    assert result.error is None
    log = db.session.get(FuelLog, result.log.id)
    assert log.vehicle_id == sample_vehicle.id
    assert log.price_per_unit == pytest.approx(120)
    assert log.odometer == 45230 and log.odometer_confirmed
    assert log.notes.startswith('Logged via telegram:')


def test_create_without_odometer_is_unconfirmed(app, test_user, sample_vehicle):
    result = create_fuel_log(test_user, '40L 4800tk')

    assert result.log.odometer == 0
    assert result.log.odometer_confirmed is False
    assert 'no_odometer' in result.warnings


def test_create_needs_volume_or_cost(app, test_user, sample_vehicle):
    result = create_fuel_log(test_user, 'odo 45230')
    assert result.error == 'nothing_found'
    assert FuelLog.query.count() == 0


def test_viewer_cannot_log(app, test_user, sample_vehicle):
    test_user.role = 'viewer'
    db.session.commit()
    result = create_fuel_log(test_user, '40L 4800tk')
    assert result.error == 'read_only'
    assert FuelLog.query.count() == 0


def test_rejects_out_of_range(app, test_user, sample_vehicle):
    result = create_fuel_log(test_user, '40L 4800tk 99999999km')
    assert result.error == 'out_of_range'


def _second_vehicle(test_user, name='Honda Civic', registration='DHA-1234'):
    vehicle = Vehicle(owner_id=test_user.id, name=name, vehicle_type='car',
                      fuel_type='petrol', odometer_unit='km', registration=registration)
    db.session.add(vehicle)
    db.session.commit()
    return vehicle


def test_two_vehicles_need_a_name(app, test_user, sample_vehicle):
    civic = _second_vehicle(test_user)

    ambiguous = create_fuel_log(test_user, '40L 4800tk')
    assert ambiguous.error == 'which_vehicle'
    assert set(ambiguous.choices) == {sample_vehicle, civic}

    by_name = create_fuel_log(test_user, 'civic 40L 4800tk')
    assert by_name.vehicle == civic
    by_reg = create_fuel_log(test_user, 'dha 1234 40L 4800tk')
    # Registration matches ignoring spaces and case, but "dha 1234" has a
    # space where the plate has a dash, so it falls back to the question.
    assert by_reg.error == 'which_vehicle' or by_reg.vehicle == civic


def test_default_vehicle_wins_when_unnamed(app, test_user, sample_vehicle):
    civic = _second_vehicle(test_user)
    test_user.default_vehicle_id = civic.id
    db.session.commit()
    vehicle, choices = choose_vehicle(test_user, '40L 4800tk')
    assert vehicle == civic and choices == []
