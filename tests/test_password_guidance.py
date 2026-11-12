"""Password fields say what they need while the password is being typed.

The rules used to be checked only by the server after submit, and a refusal
sent the form back blank with an English-only toast. Every form that sets a
password now lists the rules under the field, says whether confirm agrees,
and the forms that re-render on a refusal keep what was typed.
"""
import re

import pytest

from app import db
from app.models import AppSettings, User
from app.security import validate_password_strength

RULE_KEYS = ('length', 'upper', 'lower', 'digit')


def _rules_block(html, input_id):
    match = re.search(
        r'<ul id="%s-rules"(.*?)</ul>' % re.escape(input_id), html, re.S)
    assert match, f'no password rules for #{input_id}'
    return match.group(0)


def _assert_guidance(html, input_id, confirm_id, optional):
    block = _rules_block(html, input_id)
    for key in RULE_KEYS:
        assert f'data-rule="{key}"' in block
    assert f'data-password-confirm="{confirm_id}"' in block
    assert ('data-password-optional' in block) is optional
    assert f'data-password-match="{confirm_id}"' in html
    assert 'js/password-rules.js' in html


@pytest.fixture
def registration_open(app):
    AppSettings.set('registration_enabled', 'true')
    db.session.commit()


def test_settings_guides_an_optional_new_password(auth_client):
    html = auth_client.get('/auth/settings').get_data(as_text=True)
    _assert_guidance(html, 'new_password', 'confirm_new_password', optional=True)


def test_register_guides_a_required_password(client, registration_open):
    html = client.get('/auth/register').get_data(as_text=True)
    _assert_guidance(html, 'password', 'confirm_password', optional=False)


def test_reset_password_guides_the_new_password(client, test_user):
    token = test_user.generate_reset_token()
    db.session.commit()
    html = client.get(f'/auth/reset-password/{token}').get_data(as_text=True)
    _assert_guidance(html, 'password', 'confirm_password', optional=False)


def test_create_user_guides_the_password(admin_client):
    html = admin_client.get('/auth/users/create').get_data(as_text=True)
    _assert_guidance(html, 'password', 'confirm_password', optional=False)


def test_edit_user_guides_an_optional_password(admin_client, test_user):
    html = admin_client.get(f'/auth/users/{test_user.id}/edit').get_data(as_text=True)
    _assert_guidance(html, 'new_password', 'confirm_new_password', optional=True)


def test_rules_script_is_served(client):
    response = client.get('/static/js/password-rules.js')
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    for key in RULE_KEYS:
        assert f'{key}:' in body
    response.close()


@pytest.mark.parametrize('password', ['Abcdefg1', 'abcdefg1', 'ABCDEFG1', 'Abcdefgh', 'Abc1'])
def test_client_rules_match_the_server(password):
    """The four client rules agree with validate_password_strength."""
    client_ok = (
        len(password) >= 8
        and re.search(r'[A-Z]', password)
        and re.search(r'[a-z]', password)
        and re.search(r'\d', password)
    )
    assert bool(client_ok) == validate_password_strength(password)[0]


def test_register_keeps_username_and_email_after_a_weak_password(client, registration_open):
    response = client.post('/auth/register', data={
        'username': 'newdriver',
        'email': 'driver@example.com',
        'password': 'weakpass',
        'confirm_password': 'weakpass',
    })
    html = response.get_data(as_text=True)
    assert 'value="newdriver"' in html
    assert 'value="driver@example.com"' in html
    assert 'uppercase' in html
    assert User.query.filter_by(username='newdriver').first() is None


def test_create_user_keeps_role_and_admin_after_a_weak_password(admin_client):
    response = admin_client.post('/auth/users/create', data={
        'username': 'newviewer',
        'email': 'viewer@example.com',
        'password': 'short',
        'confirm_password': 'short',
        'role': 'viewer',
        'is_admin': 'on',
    })
    html = response.get_data(as_text=True)
    assert 'value="newviewer"' in html
    assert re.search(r'<option value="viewer"\s+selected>', html) or \
        re.search(r'<option value="viewer" selected>', html)
    assert re.search(r'name="is_admin" id="is_admin" checked', html)


def test_server_password_messages_are_translated(app):
    with app.test_request_context(headers={'Accept-Language': 'de'}):
        from flask_babel import refresh
        refresh()
        _, message = validate_password_strength('alllower1')
    assert message
    assert 'uppercase' not in message.lower()
