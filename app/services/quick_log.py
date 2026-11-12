"""Turn a short free-text message into a fuel log.

Shared by the Telegram bot and receipt-photo logging: both end up with a
line of text such as ``"40L 4800tk 45230km"`` and need the same parsing,
vehicle selection, validation and saving that the quick fuel form does.

The parser is deliberately rule-based rather than model-based so it runs
offline on a self-hosted box. It understands:

- volume: ``40L``, ``40 l``, ``40 litre(s)/liter(s)``, ``40 লিটার``
- total cost: ``4800tk``, ``৳4800``, ``4800 taka/টাকা``, ``€65.90``, ``65.90 EUR``
- price per unit: ``@120``, ``120/L``, ``120 per L``
- odometer: ``45230km``, ``45230 mi``, ``odo 45230``, ``45230 কিমি``
- partial fill: ``partial``, ``half``, ``top up``, ``আংশিক``
- a vehicle, by any word of its name or its registration

Bengali digits are accepted, and ``45,230`` is read as forty-five thousand
when the comma is followed by exactly three digits.
"""
import re
from dataclasses import dataclass, field
from datetime import date as date_cls

from app import db
from app.models import FuelLog, Vehicle

# Same limits as the fuel forms (app/routes/fuel.py).
MAX_VOLUME = 10000
MAX_UNIT_PRICE = 1_000_000
MAX_AMOUNT = 1_000_000_000
MAX_ODOMETER = 9_999_999

_BENGALI_DIGITS = str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789')

_NUMBER = r'(\d+(?:[.,]\d+)*)'
_CURRENCY_WORDS = (r'tk|taka|bdt|৳|টাকা|usd|eur|gbp|inr|chf|sek|nok|dkk|pln|'
                   r'huf|czk|try|jpy|krw|cny|clp|ars|brl|aud|cad|nzd|kr|zł|ft|'
                   r'rs|₹|\$|€|£|¥')
_VOLUME_WORDS = r'l|ltr|ltrs|litre|litres|liter|liters|লিটার|লি'
_DISTANCE_WORDS = r'km|kms|mi|miles|কিমি|কি\.মি\.'

_PRICE_RE = re.compile(
    rf'(?:@\s*{_NUMBER})|(?:{_NUMBER}\s*(?:{_CURRENCY_WORDS})?\s*(?:/|per\s+)(?:{_VOLUME_WORDS})\b)',
    re.IGNORECASE)
_VOLUME_RE = re.compile(rf'{_NUMBER}\s*(?:{_VOLUME_WORDS})(?![\w/])', re.IGNORECASE)
_COST_RE = re.compile(
    rf'(?:(?:{_CURRENCY_WORDS})\s*{_NUMBER})|(?:{_NUMBER}\s*(?:{_CURRENCY_WORDS})(?!\w))',
    re.IGNORECASE)
_ODO_RE = re.compile(
    rf'(?:(?:odo(?:meter)?|ওডো|মিটার)\s*[:=]?\s*{_NUMBER})|(?:{_NUMBER}\s*(?:{_DISTANCE_WORDS})(?!\w))',
    re.IGNORECASE)
_PARTIAL_RE = re.compile(r'\b(?:partial|half|top[\s-]?up)\b|আংশিক|অর্ধেক', re.IGNORECASE)
_BARE_NUMBER_RE = re.compile(_NUMBER)


@dataclass
class FuelDraft:
    """What a message said, before it is matched to a vehicle and saved."""
    volume: float = None
    total_cost: float = None
    price_per_unit: float = None
    odometer: float = None
    is_full_tank: bool = True
    text: str = ''
    unparsed_numbers: list = field(default_factory=list)

    @property
    def is_empty(self):
        return self.volume is None and self.total_cost is None and self.odometer is None


@dataclass
class QuickLogResult:
    log: FuelLog = None
    vehicle: Vehicle = None
    error: str = None
    # Machine-readable hints for the caller to phrase in its own language.
    warnings: list = field(default_factory=list)
    # When the vehicle is ambiguous, the candidates to ask about.
    choices: list = field(default_factory=list)


def to_number(raw):
    """Parse a number as people type it in a chat message.

    ``45,230`` and ``45.230`` with exactly three digits after a single
    separator are ambiguous; on a fuel message a three-decimal value is only
    plausible as a unit price, so we treat them as grouping only when the
    integer part is at least two digits and the result is large (an odometer
    or a cost in a high-denomination currency).
    """
    raw = raw.translate(_BENGALI_DIGITS).strip()
    if ',' in raw and '.' in raw:
        # Whichever separator comes last is the decimal one.
        if raw.rfind(',') > raw.rfind('.'):
            raw = raw.replace('.', '').replace(',', '.')
        else:
            raw = raw.replace(',', '')
    elif ',' in raw:
        parts = raw.split(',')
        if len(parts) > 2 or (len(parts[-1]) == 3 and len(parts[0]) >= 2):
            raw = raw.replace(',', '')
        else:
            raw = raw.replace(',', '.')
    elif raw.count('.') > 1:
        raw = raw.replace('.', '')
    return float(raw)


def _first_group(match):
    return next(g for g in match.groups() if g is not None)


def parse_fuel_message(text):
    """Pull the fuel figures out of ``text``. Never raises on odd input."""
    text = (text or '').translate(_BENGALI_DIGITS)
    draft = FuelDraft(text=text)
    remaining = text

    def take(regex):
        nonlocal remaining
        match = regex.search(remaining)
        if not match:
            return None
        remaining = remaining[:match.start()] + ' ' + remaining[match.end():]
        try:
            return to_number(_first_group(match))
        except (ValueError, StopIteration):
            return None

    # Order matters: "120/L" must be read as a price before "120 ... L" can
    # be read as a volume, and "4800tk" before a bare number.
    draft.price_per_unit = take(_PRICE_RE)
    draft.volume = take(_VOLUME_RE)
    draft.odometer = take(_ODO_RE)
    draft.total_cost = take(_COST_RE)
    draft.is_full_tank = not _PARTIAL_RE.search(text)

    leftovers = []
    for match in _BARE_NUMBER_RE.finditer(remaining):
        try:
            leftovers.append(to_number(match.group(1)))
        except ValueError:
            continue
    # A lone large number with no unit is almost always the odometer: people
    # type "40L 4800tk 45230" without the km.
    if draft.odometer is None:
        large = [n for n in leftovers if n >= 1000]
        if len(large) == 1:
            draft.odometer = large[0]
            leftovers.remove(large[0])
    draft.unparsed_numbers = leftovers
    return draft


def choose_vehicle(user, text):
    """Pick the vehicle a message is about.

    Returns ``(vehicle, candidates)``. A word of a vehicle's name or its
    registration in the text wins; otherwise the user's default vehicle, or
    their only active one. When none of those settle it, ``vehicle`` is None
    and ``candidates`` lists the active vehicles to choose from.
    """
    vehicles = [v for v in user.get_all_vehicles() if v.is_active is not False]
    lowered = (text or '').lower()
    words = set(re.findall(r'[\w-]+', lowered))

    def mentioned(vehicle):
        reg = (vehicle.registration or '').lower().replace(' ', '')
        if reg and reg in lowered.replace(' ', ''):
            return True
        name_words = {w for w in re.findall(r'[\w-]+', (vehicle.name or '').lower()) if len(w) >= 3}
        return bool(name_words & words)

    named = [v for v in vehicles if mentioned(v)]
    if len(named) == 1:
        return named[0], []
    if len(named) > 1:
        return None, named
    default = next((v for v in vehicles if v.id == user.default_vehicle_id), None)
    if default:
        return default, []
    if len(vehicles) == 1:
        return vehicles[0], []
    return None, vehicles


def _out_of_range(value, maximum):
    return value is not None and not (0 <= value <= maximum)


def create_fuel_log(user, text, vehicle=None, source='telegram', on_date=None):
    """Parse ``text`` and save it as a fuel log for ``user``.

    Mirrors the quick fuel form: derives the missing one of volume, price and
    total, and records nothing unless the account may write fuel logs. The
    caller commits nothing; this function commits on success.

    Warnings it may return: ``no_odometer``, ``odometer_below_last``,
    ``ignored_numbers``.
    """
    result = QuickLogResult()
    if not user.can_write('fuel'):
        result.error = 'read_only'
        return result

    draft = parse_fuel_message(text)
    if draft.volume is None and draft.total_cost is None:
        result.error = 'nothing_found'
        return result

    if vehicle is None:
        vehicle, choices = choose_vehicle(user, text)
        if vehicle is None:
            result.error = 'which_vehicle' if choices else 'no_vehicle'
            result.choices = choices
            return result
    elif vehicle not in user.get_all_vehicles():
        result.error = 'no_vehicle'
        return result
    result.vehicle = vehicle

    volume, total_cost, price = draft.volume, draft.total_cost, draft.price_per_unit
    if volume and price is not None and total_cost is None:
        total_cost = round(volume * price, 2)
    elif volume and total_cost is not None and price is None:
        price = round(total_cost / volume, 3)

    if (_out_of_range(volume, MAX_VOLUME) or _out_of_range(price, MAX_UNIT_PRICE)
            or _out_of_range(total_cost, MAX_AMOUNT)
            or _out_of_range(draft.odometer, MAX_ODOMETER)):
        result.error = 'out_of_range'
        return result

    if draft.odometer is None:
        result.warnings.append('no_odometer')
    else:
        last = vehicle.get_last_odometer()
        if last and draft.odometer < last:
            result.warnings.append('odometer_below_last')
    if draft.unparsed_numbers:
        result.warnings.append('ignored_numbers')

    log = FuelLog(
        vehicle_id=vehicle.id,
        user_id=user.id,
        date=on_date or date_cls.today(),
        # Like the fuel edit form: no reading is stored as an unconfirmed 0,
        # which consumption and distance figures skip.
        odometer=draft.odometer or 0,
        odometer_confirmed=draft.odometer is not None,
        volume=volume,
        total_cost=total_cost,
        price_per_unit=price,
        is_full_tank=draft.is_full_tank,
        notes=f'Logged via {source}: {draft.text.strip()}'[:500],
    )
    db.session.add(log)
    db.session.commit()
    result.log = log
    return result
