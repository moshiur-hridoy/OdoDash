"""Tests for the public demo mode (app/demo.py)."""
from datetime import date

import pytest

from app import create_app, db as _db_ext
from app.models import Expense, FuelLog, Trip, User, Vehicle
from tests.conftest import TestConfig


class DemoConfig(TestConfig):
    DEMO_MODE = True


@pytest.fixture
def demo_app():
    flask_app = create_app(DemoConfig)
    ctx = flask_app.app_context()
    ctx.push()
    yield flask_app
    _db_ext.session.remove()
    _db_ext.drop_all()
    ctx.pop()


@pytest.fixture
def demo_client(demo_app):
    client = demo_app.test_client()
    client.post('/auth/login', data={'username': 'demo', 'password': 'demo'})
    return client


def test_seeds_demo_account_and_history(demo_app):
    user = User.query.filter_by(username='demo').one()
    assert user.is_admin and user.check_password('demo')
    assert Vehicle.query.count() == 2
    assert FuelLog.query.count() > 15
    assert FuelLog.query.filter_by(vehicle_id=Vehicle.query.filter_by(name='Weekend Ride').one().id).count() > 15
    assert Expense.query.count() > 10
    assert Trip.query.count() > 10


def test_login_page_shows_credentials(demo_app):
    html = demo_app.test_client().get('/auth/login').get_data(as_text=True)
    assert 'Live demo' in html
    assert 'value="demo"' in html


@pytest.mark.parametrize('path', ['/', '/fuel/', '/expenses/', '/trips/', '/charging/', '/auth/settings'])
def test_seeded_pages_render(demo_client, path):
    assert demo_client.get(path, follow_redirects=True).status_code == 200


def test_password_change_is_refused(demo_client):
    demo_client.post('/auth/settings', data={
        'email': 'demo@example.com', 'new_password': 'Hijacked123!',
        'confirm_new_password': 'Hijacked123!',
    })
    assert User.query.filter_by(username='demo').one().check_password('demo')


def test_preferences_can_still_change(demo_client):
    demo_client.post('/auth/settings', data={'email': 'demo@example.com', 'currency': 'EUR'})
    assert User.query.filter_by(username='demo').one().currency == 'EUR'


def test_user_deletion_is_refused(demo_client):
    user = User.query.filter_by(username='demo').one()
    demo_client.post(f'/auth/users/{user.id}/delete')
    assert db_user_exists('demo')


def test_registration_is_refused(demo_app):
    demo_app.test_client().post('/auth/register', data={
        'username': 'intruder', 'email': 'x@example.com',
        'password': 'Intruder123!', 'confirm_password': 'Intruder123!',
    })
    assert not db_user_exists('intruder')


def test_api_refusal_is_json(demo_client):
    response = demo_client.post('/api/notifications/test')
    assert response.status_code == 403
    assert response.get_json()['code'] == 'demo_mode'


def test_vehicle_data_stays_editable(demo_client):
    vehicle = Vehicle.query.filter_by(name='Daily Driver').one()
    before = Expense.query.count()
    demo_client.post('/expenses/new', data={
        'vehicle_id': vehicle.id, 'date': date.today().isoformat(),
        'category': 'parking', 'description': 'Visitor test', 'cost': '5',
    })
    assert Expense.query.count() == before + 1


def test_off_by_default(app):
    assert not app.config.get('DEMO_MODE')
    assert User.query.filter_by(username='demo').first() is None


def db_user_exists(username):
    return User.query.filter_by(username=username).first() is not None
