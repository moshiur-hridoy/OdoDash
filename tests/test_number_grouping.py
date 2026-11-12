"""Distances and odometer readings follow the thousand-separator preference.

The vehicle page grouped the last odometer (8,627 km) while the total
distance beside it and the dashboard, fuel, expense and PDF figures printed
raw digits (7405 km), so the same page mixed two formats.
"""
from datetime import date

import pytest

from app import db
from app.models import Expense, FuelLog


@pytest.fixture
def long_history(app, test_user, sample_vehicle):
    test_user.thousand_separator = 'comma'
    test_user.distance_unit = 'km'
    for day, odometer in ((1, 10000.0), (20, 22345.0)):
        db.session.add(FuelLog(
            vehicle_id=sample_vehicle.id, user_id=test_user.id,
            date=date(2024, 1, day), odometer=odometer, volume=40.0,
            price_per_unit=1.5, total_cost=60.0, is_full_tank=True,
        ))
    db.session.add(Expense(
        vehicle_id=sample_vehicle.id, user_id=test_user.id,
        date=date(2024, 1, 10), category='maintenance',
        description='Service', cost=75.0, odometer=15500.0,
    ))
    db.session.commit()
    return sample_vehicle


def _page(client, url):
    resp = client.get(url)
    assert resp.status_code == 200
    return resp.get_data(as_text=True)


def test_vehicle_page_groups_total_distance(auth_client, long_history):
    html = _page(auth_client, f'/vehicles/{long_history.id}')
    assert '12,345' in html
    assert '12345' not in html


def test_dashboard_groups_total_distance(auth_client, long_history):
    html = _page(auth_client, '/dashboard')
    assert '12,345' in html


def test_fuel_list_groups_odometer(auth_client, long_history):
    html = _page(auth_client, '/fuel/')
    assert '22,345' in html
    assert '22345 ' not in html


def test_expense_list_groups_odometer(auth_client, long_history):
    html = _page(auth_client, '/expenses/')
    assert '15,500' in html


def test_no_separator_preference_keeps_plain_digits(auth_client, long_history, test_user):
    test_user.thousand_separator = 'none'
    db.session.commit()
    html = _page(auth_client, f'/vehicles/{long_history.id}')
    assert '12345' in html
    assert '12,345' not in html
