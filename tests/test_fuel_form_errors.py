"""A refused fuel log keeps what the user typed.

Every validation failure used to redirect to a blank form, so one bad field
meant retyping the date, odometer, volume, price, station and notes. The form
now comes back with the typed values, the message under the field that
failed, and that field focused.
"""
import re

from app import db
from app.models import FuelLog


def _tag(html, name, tag='input'):
    match = re.search(r'<%s[^>]*\bname="%s"[^>]*>' % (tag, name), html, re.S)
    assert match, f'no <{tag} name="{name}"> in the page'
    return match.group(0)


def _value(html, name):
    match = re.search(r'\bvalue="([^"]*)"', _tag(html, name))
    return match.group(1) if match else None


def _post_new(client, vehicle, **overrides):
    data = {
        'vehicle_id': str(vehicle.id),
        'date': '2024-04-03',
        'odometer': '16200',
        'volume': '40.5',
        'price_per_unit': '1.50',
        'station': 'Corner Garage',
        'notes': 'Before the <long> trip',
        'sales_tax': '-5',
    }
    data.update(overrides)
    return client.post('/fuel/new', data=data)


def test_new_log_keeps_typed_values_after_a_refusal(auth_client, sample_vehicle):
    resp = _post_new(auth_client, sample_vehicle)
    html = resp.get_data(as_text=True)

    assert resp.status_code == 422
    assert FuelLog.query.count() == 0
    assert _value(html, 'date') == '2024-04-03'
    assert _value(html, 'odometer') == '16200'
    assert _value(html, 'volume') == '40.5'
    assert _value(html, 'price_per_unit') == '1.50'
    assert _value(html, 'station') == 'Corner Garage'
    assert 'Before the &lt;long&gt; trip</textarea>' in html


def test_only_the_failing_field_is_marked(auth_client, sample_vehicle):
    html = _post_new(auth_client, sample_vehicle).get_data(as_text=True)

    sales_tax = _tag(html, 'sales_tax')
    assert 'aria-invalid="true"' in sales_tax
    assert 'aria-describedby="sales_tax-error"' in sales_tax
    assert 'autofocus' in sales_tax
    assert re.search(r'id="sales_tax-error"[^>]*>\s*Sales tax cannot be negative', html)
    assert html.count(' aria-invalid="true" aria-describedby=') == 1
    assert 'aria-invalid' not in _tag(html, 'volume')


def test_unticked_full_tank_stays_unticked(auth_client, sample_vehicle):
    # A new form ticks "full tank" by default; a refused one must not re-tick it.
    html = _post_new(auth_client, sample_vehicle).get_data(as_text=True)
    assert 'checked' not in _tag(html, 'is_full_tank')

    html = _post_new(auth_client, sample_vehicle, is_full_tank='on',
                     is_missed='on').get_data(as_text=True)
    assert 'checked' in _tag(html, 'is_full_tank')
    assert 'checked' in _tag(html, 'is_missed')


def test_return_to_vehicle_survives_a_refusal(auth_client, sample_vehicle):
    html = _post_new(auth_client, sample_vehicle,
                     return_to='vehicle').get_data(as_text=True)
    assert 'name="return_to" value="vehicle"' in html


def test_edit_shows_typed_values_and_leaves_the_log_unchanged(auth_client, sample_fuel_log):
    resp = auth_client.post(f'/fuel/{sample_fuel_log.id}/edit', data={
        'vehicle_id': str(sample_fuel_log.vehicle_id),
        'date': '2024-01-16',
        'odometer': '-1',
        'volume': '42.25',
        'price_per_unit': '1.55',
        'total_cost': '65.49',
        'notes': 'corrected receipt',
    })
    html = resp.get_data(as_text=True)

    assert resp.status_code == 422
    assert _value(html, 'odometer') == '-1'
    assert _value(html, 'volume') == '42.25'
    assert 'corrected receipt</textarea>' in html
    assert 'aria-invalid="true"' in _tag(html, 'odometer')

    db.session.refresh(sample_fuel_log)
    assert sample_fuel_log.odometer == 10000.0
    assert sample_fuel_log.volume == 40.0
    assert sample_fuel_log.notes is None


def test_few_vehicles_are_picked_from_cards(auth_client, sample_vehicle):
    html = auth_client.get('/fuel/new').get_data(as_text=True)
    assert re.search(r'<input type="radio" name="vehicle_id" value="%d" required checked' % sample_vehicle.id, html)
    assert '<select name="vehicle_id"' not in html


def test_many_vehicles_fall_back_to_a_select(auth_client, sample_vehicle, test_user):
    from app.models import Vehicle
    for n in range(4):
        db.session.add(Vehicle(owner_id=test_user.id, name=f'Extra {n}', vehicle_type='car', fuel_type='petrol'))
    db.session.commit()
    html = auth_client.get('/fuel/new').get_data(as_text=True)
    assert '<select name="vehicle_id" id="vehicle_id"' in html
    assert 'type="radio" name="vehicle_id"' not in html


def _saved_station(user, name='Test Station', brand='BP'):
    from app.models import FuelStation
    station = FuelStation(user_id=user.id, name=name, brand=brand)
    db.session.add(station)
    db.session.commit()
    return station


def _station_menu(html):
    match = re.search(r'<select id="station_choice".*?</select>', html, re.S)
    assert match, 'no station menu in the page'
    return match.group(0)


def test_saved_stations_are_a_select_menu(auth_client, sample_vehicle, test_user):
    station = _saved_station(test_user)
    html = auth_client.get('/fuel/new').get_data(as_text=True)
    menu = _station_menu(html)
    assert f'<option value="{station.id}" data-name="Test Station (BP)">' in menu
    assert 'datalist' not in html
    # Any other name is still typed into the box beside the menu.
    assert 'list=' not in _tag(html, 'station')
    assert _value(html, 'station') == ''
    assert _value(html, 'station_id') == ''


def test_without_saved_stations_only_the_text_box_is_shown(auth_client, sample_vehicle):
    html = auth_client.get('/fuel/new').get_data(as_text=True)
    assert 'id="station_choice"' not in html
    assert 'name="station"' in html
    assert '/stations/new' in html


def test_a_refused_save_keeps_the_station_link(auth_client, sample_vehicle, test_user):
    station = _saved_station(test_user)
    html = _post_new(auth_client, sample_vehicle, station='Test Station (BP)',
                     station_id=str(station.id)).get_data(as_text=True)
    assert _value(html, 'station_id') == str(station.id)
    assert f'<option value="{station.id}" data-name="Test Station (BP)" selected>' in _station_menu(html)


def test_editing_selects_the_matching_station_without_linking_it(
        auth_client, sample_fuel_log, test_user):
    station = _saved_station(test_user)
    sample_fuel_log.station = 'Test Station (BP)'
    db.session.commit()
    html = auth_client.get(f'/fuel/{sample_fuel_log.id}/edit').get_data(as_text=True)
    assert f'value="{station.id}" data-name="Test Station (BP)" selected' in _station_menu(html)
    assert _value(html, 'station') == 'Test Station (BP)'
    # Opening a log never attaches it to a station it was not saved with.
    assert _value(html, 'station_id') == ''


def test_editing_a_log_with_another_name_selects_no_station(
        auth_client, sample_fuel_log, test_user):
    _saved_station(test_user)
    sample_fuel_log.station = 'Clean Fuel Mohakhali (Mobil)'
    db.session.commit()
    html = auth_client.get(f'/fuel/{sample_fuel_log.id}/edit').get_data(as_text=True)
    assert ' selected' not in _station_menu(html)
    assert _value(html, 'station') == 'Clean Fuel Mohakhali (Mobil)'


def test_more_details_opens_for_a_refused_optional_field(auth_client, sample_vehicle):
    html = auth_client.get('/fuel/new').get_data(as_text=True)
    assert '<details class="ds-card form-more">' in html
    html = _post_new(auth_client, sample_vehicle).get_data(as_text=True)  # sales tax refused
    assert '<details class="ds-card form-more" open>' in html
