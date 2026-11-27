"""A login cookie belongs to one account, not to whoever holds its id."""
import pytest
from flask import g

from app import db, _backfill_session_tokens
from app.models import User

PASSWORD = 'TestPass123!'

# Flask-Login itself still uses a deprecated clock call for the remember cookie
pytestmark = pytest.mark.filterwarnings('ignore::DeprecationWarning:flask_login.login_manager')


@pytest.fixture(autouse=True)
def _forget_cached_user(app):
    # The app fixture keeps one app context alive, so Flask-Login's cached user
    # on `g` would otherwise carry over between clients.
    app.before_request_funcs.setdefault(None, []).insert(
        0, lambda: g.pop('_login_user', None) and None)


def _make_user(name):
    user = User(username=name, email=f'{name}@example.com')
    user.set_password(PASSWORD)
    db.session.add(user)
    db.session.commit()
    return user


def _signed_in(app, user, remember=False):
    client = app.test_client()
    data = {'username': user.username, 'password': PASSWORD}
    if remember:
        data['remember'] = 'on'
    assert client.post('/auth/login', data=data).status_code == 302
    return client


def _is_signed_in(client):
    return client.get('/auth/settings').status_code == 200


def _replace_account(user):
    old_id = user.id
    db.session.delete(user)
    db.session.commit()
    newcomer = _make_user('newcomer')
    assert newcomer.id == old_id, 'SQLite is expected to reuse the id here'
    return newcomer


@pytest.mark.parametrize('remember', [False, True])
def test_a_deleted_accounts_cookie_does_not_open_the_next_one(app, remember):
    gone = _make_user('gone')
    stale = _signed_in(app, gone, remember)
    assert _is_signed_in(stale)

    _replace_account(gone)

    assert not _is_signed_in(stale)


def test_remember_me_survives_a_lost_session(app):
    client = _signed_in(app, _make_user('keeper'), remember=True)
    client.delete_cookie('session', domain='localhost')
    assert _is_signed_in(client)


@pytest.mark.parametrize('cookie', ['{id}', '{id}:', '{id}:wrong', 'nonsense', ''])
def test_a_cookie_without_the_right_token_is_refused(app, cookie):
    user = _make_user('keeper')
    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = cookie.format(id=user.id)
    assert not _is_signed_in(client)


def test_older_accounts_get_a_token_and_keep_it(app):
    user = _make_user('older')
    user.session_token = None
    db.session.commit()

    _backfill_session_tokens()
    db.session.expire_all()
    token = user.session_token
    assert token

    _backfill_session_tokens()
    db.session.expire_all()
    assert user.session_token == token
    assert _is_signed_in(_signed_in(app, user))
