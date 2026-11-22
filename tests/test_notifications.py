"""Tests for the notification service (ntfy auth behaviour, #90)."""
from unittest.mock import patch

from app.services.notifications import NotificationService


class TestSendNtfy:
    def test_refuses_token_over_plain_http(self, app):
        """An access token must never be sent over an unencrypted connection."""
        success, error = NotificationService.send_ntfy(
            'http://ntfy.example.com/topic', 'Title', 'Message', token='tk_secret'
        )
        assert success is False
        assert 'plain HTTP' in error

    def test_plain_http_without_token_still_allowed(self, app):
        """Existing tokenless self-hosted HTTP setups keep working."""
        with patch('app.services.notifications.urlopen') as mock_open:
            mock_open.return_value.__enter__.return_value = object()
            success, error = NotificationService.send_ntfy(
                'http://ntfy.lan/topic', 'Title', 'Message'
            )
        assert success is True
        req = mock_open.call_args[0][0]
        assert not req.has_header('Authorization')

    def test_token_sent_as_bearer_over_https(self, app):
        with patch('app.services.notifications.urlopen') as mock_open:
            mock_open.return_value.__enter__.return_value = object()
            success, error = NotificationService.send_ntfy(
                'https://ntfy.example.com/topic', 'Title', 'Message', token='tk_secret'
            )
        assert success is True
        req = mock_open.call_args[0][0]
        assert req.get_header('Authorization') == 'Bearer tk_secret'

    def test_bare_topic_gets_no_header_without_token(self, app):
        with patch('app.services.notifications.urlopen') as mock_open:
            mock_open.return_value.__enter__.return_value = object()
            success, error = NotificationService.send_ntfy(
                'my-topic', 'Title', 'Message'
            )
        assert success is True
        req = mock_open.call_args[0][0]
        assert req.full_url == 'https://ntfy.sh/my-topic'


class TestSendTelegram:
    def test_needs_bot_token(self, app):
        success, error = NotificationService.send_telegram('123', 'Title', 'Message')
        assert success is False
        assert 'not configured' in error

    def test_needs_linked_chat(self, app):
        with patch('app.services.telegram_bot.get_token', return_value='tok'):
            success, error = NotificationService.send_telegram(None, 'Title', 'Message')
        assert success is False
        assert 'not linked' in error

    def test_sends_message_to_chat(self, app):
        with patch('app.services.telegram_bot.get_token', return_value='tok'), \
                patch('app.services.telegram_bot.api_call') as api_call:
            success, error = NotificationService.send_telegram('123', 'Title', 'Message')
        assert success is True
        api_call.assert_called_once_with('tok', 'sendMessage', chat_id='123',
                                         text='Title\n\nMessage')

    def test_telegram_error_is_reported(self, app):
        from app.services.telegram_bot import TelegramError
        with patch('app.services.telegram_bot.get_token', return_value='tok'), \
                patch('app.services.telegram_bot.api_call', side_effect=TelegramError('blocked')):
            success, error = NotificationService.send_telegram('123', 'Title', 'Message')
        assert success is False
        assert error == 'blocked'
