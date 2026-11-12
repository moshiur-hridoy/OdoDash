"""Telegram bot: linking a chat, logging fuel, undo, and the settings routes."""
from datetime import timedelta

import pytest

from app import db
from app.models import AppSettings, FuelLog, User
from app.services import telegram_bot
from app.utils import utcnow

CHAT_ID = '424242'


def _message(text, chat_id=CHAT_ID, chat_type='private', **extra):
    message = {'chat': {'id': int(chat_id), 'type': chat_type}, 'text': text}
    message.update(extra)
    return {'update_id': 1, 'message': message}


def _reply(text, **kwargs):
    result = telegram_bot.reply_for_update(_message(text, **kwargs))
    return result[1] if result else None


@pytest.fixture
def linked_user(app, test_user):
    test_user.telegram_chat_id = CHAT_ID
    db.session.commit()
    return test_user


class TestLinking:
    def test_valid_code_links_the_chat(self, app, test_user):
        code = telegram_bot.new_link_code(test_user)

        reply = _reply(f'/start {code}')

        db.session.refresh(test_user)
        assert test_user.telegram_chat_id == CHAT_ID
        assert test_user.telegram_link_code is None
        assert 'testuser' in reply

    def test_code_is_case_insensitive(self, app, test_user):
        code = telegram_bot.new_link_code(test_user)
        _reply(f'/start {code.lower()}')
        db.session.refresh(test_user)
        assert test_user.telegram_chat_id == CHAT_ID

    def test_expired_code_is_refused(self, app, test_user):
        code = telegram_bot.new_link_code(test_user)
        test_user.telegram_link_expires = utcnow() - timedelta(minutes=1)
        db.session.commit()

        reply = _reply(f'/start {code}')

        db.session.refresh(test_user)
        assert test_user.telegram_chat_id is None
        assert 'expired' in reply

    def test_unlinked_chat_is_told_how_to_link(self, app, test_user):
        reply = _reply('40L 4800tk')
        assert 'not linked' in reply
        assert FuelLog.query.count() == 0

    def test_group_chats_are_ignored(self, app, linked_user, sample_vehicle):
        assert telegram_bot.reply_for_update(
            _message('40L 4800tk', chat_type='group')) is None
        assert FuelLog.query.count() == 0

    def test_unlink_command(self, app, linked_user):
        _reply('/unlink')
        db.session.refresh(linked_user)
        assert linked_user.telegram_chat_id is None


class TestLogging:
    def test_message_becomes_fuel_log(self, app, linked_user, sample_vehicle):
        reply = _reply('40L 4800tk 45230km')

        log = FuelLog.query.one()
        assert log.vehicle_id == sample_vehicle.id
        assert log.volume == 40 and log.total_cost == 4800
        assert sample_vehicle.name in reply
        assert '/undo' in reply

    def test_unreadable_message_saves_nothing(self, app, linked_user, sample_vehicle):
        reply = _reply('what is my mileage?')
        assert FuelLog.query.count() == 0
        assert 'could not find' in reply

    def test_photo_without_text_explains(self, app, linked_user, sample_vehicle):
        update = _message('', photo=[{'file_id': 'x'}])
        update['message'].pop('text')
        _chat, reply = telegram_bot.reply_for_update(update)
        assert 'Photos' in reply
        assert FuelLog.query.count() == 0

    def test_undo_removes_the_bot_entry(self, app, linked_user, sample_vehicle):
        _reply('40L 4800tk 45230km')
        reply = _reply('/undo')
        assert FuelLog.query.count() == 0
        assert sample_vehicle.name in reply

    def test_undo_leaves_web_entries_alone(self, app, linked_user, sample_vehicle):
        db.session.add(FuelLog(vehicle_id=sample_vehicle.id, user_id=linked_user.id,
                               date=utcnow().date(), odometer=100, volume=10))
        db.session.commit()
        reply = _reply('/undo')
        assert FuelLog.query.count() == 1
        assert 'Nothing to undo' in reply

    def test_reply_uses_the_users_language(self, app, linked_user, sample_vehicle):
        linked_user.language = 'de'
        db.session.commit()
        # Untranslated strings fall back to English; the call must not fail
        # outside a request context.
        assert _reply('/help')


class TestPolling:
    def test_poll_answers_and_advances_offset(self, app, linked_user, sample_vehicle, monkeypatch):
        calls = []

        def fake_api(token, method, http_timeout=10, **params):
            calls.append((method, params))
            if method == 'getUpdates':
                return [dict(_message('40L 4800tk 45230km'), update_id=7)]
            return {}

        monkeypatch.setattr(telegram_bot, 'api_call', fake_api)

        assert telegram_bot.poll_once('token') == 1
        assert FuelLog.query.count() == 1
        assert calls[1][0] == 'sendMessage'
        assert calls[1][1]['chat_id'] == CHAT_ID
        assert AppSettings.get(telegram_bot.SETTING_OFFSET) == '8'

    def test_failing_update_is_skipped_not_retried(self, app, linked_user, monkeypatch):
        def fake_api(token, method, http_timeout=10, **params):
            if method == 'getUpdates':
                return [dict(_message('40L'), update_id=3)]
            raise telegram_bot.TelegramError('send failed')

        monkeypatch.setattr(telegram_bot, 'api_call', fake_api)
        telegram_bot.poll_once('token')
        assert AppSettings.get(telegram_bot.SETTING_OFFSET) == '4'


class TestRoutes:
    def test_admin_saves_a_valid_token(self, admin_client, app, monkeypatch):
        monkeypatch.setattr(telegram_bot, 'check_token', lambda token: 'odo_bot')
        response = admin_client.post('/auth/telegram-settings',
                                     data={'telegram_bot_token': '123:abc'},
                                     follow_redirects=True)
        assert response.status_code == 200
        assert AppSettings.get(telegram_bot.SETTING_TOKEN) == '123:abc'
        assert AppSettings.get(telegram_bot.SETTING_USERNAME) == 'odo_bot'

    def test_rejected_token_is_not_saved(self, admin_client, app, monkeypatch):
        def refuse(token):
            raise telegram_bot.TelegramError('Unauthorized')
        monkeypatch.setattr(telegram_bot, 'check_token', refuse)
        admin_client.post('/auth/telegram-settings', data={'telegram_bot_token': 'bad'})
        assert not AppSettings.get(telegram_bot.SETTING_TOKEN)

    def test_non_admin_cannot_set_token(self, auth_client, app):
        auth_client.post('/auth/telegram-settings', data={'telegram_bot_token': 'x'})
        assert not AppSettings.get(telegram_bot.SETTING_TOKEN)

    def test_link_shows_a_code(self, auth_client, app, test_user):
        AppSettings.set(telegram_bot.SETTING_TOKEN, '123:abc')
        AppSettings.set(telegram_bot.SETTING_USERNAME, 'odo_bot')

        response = auth_client.post('/auth/telegram/link', follow_redirects=True)

        user = db.session.get(User, test_user.id)
        assert user.telegram_link_code
        assert f'/start {user.telegram_link_code}'.encode() in response.data
        assert b't.me/odo_bot?start=' in response.data

    def test_token_is_not_shown_to_non_admins(self, auth_client, app):
        AppSettings.set(telegram_bot.SETTING_TOKEN, '123:secret-token')
        response = auth_client.get('/auth/settings')
        assert b'secret-token' not in response.data

    def test_viewer_may_link(self, auth_client, app, test_user):
        AppSettings.set(telegram_bot.SETTING_TOKEN, '123:abc')
        test_user.role = 'viewer'
        db.session.commit()
        auth_client.post('/auth/telegram/link')
        assert db.session.get(User, test_user.id).telegram_link_code
