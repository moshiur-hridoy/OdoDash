"""Log fuel by messaging a Telegram bot.

An admin creates a bot with @BotFather and pastes its token into Settings.
Each user links their private chat once: Settings gives them a one-time code
(and a t.me deep link carrying it), and sending ``/start CODE`` to the bot
ties that chat to their account. After that, a message such as
``40L 4800tk 45230km`` becomes a fuel log, parsed by
:mod:`app.services.quick_log` exactly as the receipt-photo path does.

The bot uses long polling (``getUpdates``) rather than a webhook, so it works
on a home server with no public URL. Polling runs in the background
scheduler process, which the scheduler lock limits to one per instance, so
two workers never answer the same message.
"""
import logging
import secrets
import time
from datetime import timedelta

import requests
from flask_babel import force_locale, gettext as _

from app import db
from app.models import AppSettings, FuelLog, User
from app.services.quick_log import create_fuel_log
from app.utils import utcnow

logger = logging.getLogger(__name__)

SETTING_TOKEN = 'telegram_bot_token'
SETTING_USERNAME = 'telegram_bot_username'
SETTING_OFFSET = 'telegram_update_offset'

API_URL = 'https://api.telegram.org/bot{token}/{method}'
LONG_POLL_SECONDS = 25
LINK_CODE_TTL = timedelta(minutes=15)
UNDO_WINDOW = timedelta(minutes=30)
SOURCE = 'telegram'
# Unambiguous characters only: no 0/O or 1/I/L.
_CODE_ALPHABET = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'


class TelegramError(Exception):
    """The Telegram Bot API refused a request or could not be reached."""


def get_token():
    return (AppSettings.get(SETTING_TOKEN) or '').strip()


def is_enabled():
    return bool(get_token())


def bot_username():
    return AppSettings.get(SETTING_USERNAME) or ''


def api_call(token, method, http_timeout=10, **params):
    """Call a Bot API method and return its ``result``.

    ``params`` go to Telegram as the JSON body; ``http_timeout`` is ours.
    """
    try:
        response = requests.post(API_URL.format(token=token, method=method),
                                 json=params, timeout=http_timeout)
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise TelegramError(str(exc)) from exc
    if not data.get('ok'):
        raise TelegramError(data.get('description') or f'HTTP {response.status_code}')
    return data.get('result')


def check_token(token):
    """Return the bot's username for ``token``, or raise TelegramError."""
    me = api_call(token, 'getMe')
    return me.get('username') or ''


# --- Linking -----------------------------------------------------------

def new_link_code(user):
    """Give ``user`` a fresh one-time code to send the bot."""
    code = ''.join(secrets.choice(_CODE_ALPHABET) for _ in range(8))
    user.telegram_link_code = code
    user.telegram_link_expires = utcnow() + LINK_CODE_TTL
    db.session.commit()
    return code


def unlink(user):
    user.telegram_chat_id = None
    user.telegram_link_code = None
    user.telegram_link_expires = None
    db.session.commit()


def _link_chat(code, chat_id):
    """Link ``chat_id`` to the account holding ``code``. Returns the user."""
    code = (code or '').strip().upper()
    if not code:
        return None
    user = User.query.filter_by(telegram_link_code=code).first()
    if not user or not user.telegram_link_expires or user.telegram_link_expires < utcnow():
        return None
    # A chat belongs to one account: move it if another account had it.
    User.query.filter(User.telegram_chat_id == chat_id, User.id != user.id).update(
        {User.telegram_chat_id: None}, synchronize_session=False)
    user.telegram_chat_id = chat_id
    user.telegram_link_code = None
    user.telegram_link_expires = None
    db.session.commit()
    return user


# --- Replies -----------------------------------------------------------

def _number(value):
    if value is None:
        return None
    return f'{value:,.2f}'.rstrip('0').rstrip('.') if value % 1 else f'{value:,.0f}'


def _help_text():
    return _(
        'Send a fill-up as one line, for example:\n'
        '40L 4800tk 45230km\n'
        '35.5 l @120 odo 45230 partial\n\n'
        'Add a vehicle name if you have more than one. '
        '/undo removes the last entry, /unlink disconnects this chat.'
    )


def _saved_text(result, user):
    log = result.log
    parts = []
    if log.volume is not None:
        parts.append(f'{_number(log.volume)} {user.volume_unit or "L"}')
    if log.total_cost is not None:
        parts.append(f'{_number(log.total_cost)} {user.currency or ""}'.strip())
    if log.odometer_confirmed:
        parts.append(f'{_number(log.odometer)} {result.vehicle.get_effective_odometer_unit()}')
    parts.append(_('full tank') if log.is_full_tank else _('partial fill'))
    lines = [_('Saved for %(vehicle)s: %(details)s',
               vehicle=result.vehicle.name, details=' · '.join(parts))]
    if 'no_odometer' in result.warnings:
        lines.append(_('No odometer reading, so this fill-up will not count towards consumption.'))
    if 'odometer_below_last' in result.warnings:
        lines.append(_('The odometer is lower than the last reading for this vehicle. Check it, or /undo.'))
    if 'ignored_numbers' in result.warnings:
        lines.append(_('Some numbers were not understood and were left out.'))
    lines.append(_('/undo to remove it.'))
    return '\n'.join(lines)


def _error_text(result):
    if result.error == 'read_only':
        return _('Your account cannot add fuel logs.')
    if result.error == 'which_vehicle':
        names = ', '.join(v.name for v in result.choices)
        return _('Which vehicle? Send the message again with one of: %(names)s', names=names)
    if result.error == 'no_vehicle':
        return _('There is no vehicle on your account to log this against.')
    if result.error == 'out_of_range':
        return _('One of those numbers is too large. Nothing was saved.')
    return _('I could not find a volume or a cost in that message.') + '\n\n' + _help_text()


def _undo(user):
    log = (FuelLog.query
           .filter(FuelLog.user_id == user.id,
                   FuelLog.notes.like(f'Logged via {SOURCE}:%'),
                   FuelLog.created_at >= utcnow() - UNDO_WINDOW)
           .order_by(FuelLog.id.desc())
           .first())
    if not log:
        return _('Nothing to undo from the last 30 minutes.')
    vehicle_name = log.vehicle.name if log.vehicle else ''
    db.session.delete(log)
    db.session.commit()
    return _('Removed the last fill-up for %(vehicle)s.', vehicle=vehicle_name)


# --- Update handling -----------------------------------------------------

def reply_for_update(update):
    """Work out the reply to one Telegram update.

    Returns ``(chat_id, text)``, or None when the update should be ignored
    (not a private-chat message). Separate from sending so it can be tested
    without the network.
    """
    message = update.get('message')
    if not message:
        return None
    chat = message.get('chat') or {}
    if chat.get('type') != 'private':
        return None
    chat_id = str(chat.get('id'))
    text = (message.get('text') or message.get('caption') or '').strip()
    command, _sep, argument = text.partition(' ')
    command = command.split('@', 1)[0].lower()

    if command == '/start' and argument.strip():
        user = _link_chat(argument, chat_id)
        if not user:
            # No account yet, so no language preference: answer in English.
            with force_locale('en'):
                return chat_id, _('That code is not valid or has expired. '
                                  'Get a new one from Settings in OdoDash.')
        with force_locale(user.language or 'en'):
            return chat_id, (_('Linked to %(username)s.', username=user.username)
                             + '\n\n' + _help_text())

    user = User.query.filter_by(telegram_chat_id=chat_id).first()
    if not user:
        with force_locale('en'):
            return chat_id, _('This chat is not linked to an OdoDash account yet. '
                              'Open Settings in OdoDash, choose Connect Telegram, '
                              'and send the code it shows here.')

    with force_locale(user.language or 'en'):
        if command in ('/start', '/help'):
            return chat_id, _help_text()
        if command == '/undo':
            return chat_id, _undo(user)
        if command == '/unlink':
            unlink(user)
            return chat_id, _('This chat is no longer linked. You can link it again from Settings.')
        if message.get('photo') and not text:
            return chat_id, _('Photos are not read yet. Send the fill-up as text, for example: 40L 4800tk 45230km')
        result = create_fuel_log(user, text, source=SOURCE)
        if result.error:
            return chat_id, _error_text(result)
        return chat_id, _saved_text(result, user)


def poll_once(token, timeout=LONG_POLL_SECONDS):
    """Fetch pending updates, answer them, and remember how far we got."""
    offset = int(AppSettings.get(SETTING_OFFSET) or 0)
    updates = api_call(token, 'getUpdates', http_timeout=timeout + 10,
                       offset=offset, allowed_updates=['message'], timeout=timeout)
    for update in updates or []:
        try:
            reply = reply_for_update(update)
            if reply:
                api_call(token, 'sendMessage', chat_id=reply[0], text=reply[1],
                         disable_web_page_preview=True)
        except Exception:  # noqa: BLE001 - one bad update must not stall the queue
            db.session.rollback()
            logger.exception('Telegram update %s failed', update.get('update_id'))
        # Advance past this update whatever happened, so a message that
        # keeps failing is not retried forever.
        AppSettings.set(SETTING_OFFSET, str(update['update_id'] + 1))
    return len(updates or [])


def run_polling_loop(app, idle_seconds=60, error_seconds=30):
    """Poll forever. Started once per instance by the background scheduler."""
    while True:
        try:
            with app.app_context():
                token = get_token()
                if not token:
                    time.sleep(idle_seconds)
                    continue
                poll_once(token)
        except TelegramError as exc:
            logger.warning('Telegram polling failed: %s', exc)
            time.sleep(error_seconds)
        except Exception:  # noqa: BLE001 - keep the bot alive
            logger.exception('Telegram polling crashed')
            time.sleep(error_seconds)
