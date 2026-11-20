"""Fixed-payment estimates using a nominal annual rate and end-of-period payments."""
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from decimal import Decimal, ROUND_HALF_UP, localcontext
from math import isfinite

from app.utils import parse_decimal

PER_YEAR = {'weekly': 52, 'biweekly': 26, 'monthly': 12, 'quarterly': 4,
            'biannual': 2, 'yearly': 1}
CENT = Decimal('0.01')


def validate_terms(raw):
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError('Invalid loan terms')
    frequency = raw.get('frequency')
    if frequency not in PER_YEAR:
        raise ValueError('Invalid loan frequency')
    rate = parse_decimal(raw.get('annual_rate'))
    if rate is None or not isfinite(rate) or not 0 <= rate <= 100:
        raise ValueError('Invalid annual rate')
    term = int(str(raw.get('term', '')))
    unit = raw.get('term_unit')
    if unit not in ('months', 'payments') or not 1 <= term <= 5200:
        raise ValueError('Invalid term')
    first = date.fromisoformat(str(raw.get('first_payment', '')))
    terms = dict(annual_rate=rate, frequency=frequency, first_payment=first.isoformat(),
                 term=term, term_unit=unit)
    if not 1 <= payment_count(terms) <= PER_YEAR[frequency] * 100:
        raise ValueError('Invalid number of payments')
    return terms


def payment_count(terms):
    if terms['term_unit'] == 'payments':
        return terms['term']
    periods = Decimal(terms['term'] * PER_YEAR[terms['frequency']]) / 12
    return int(periods.to_integral_value(rounding=ROUND_HALF_UP))


def payment_number(terms, day):
    first = date.fromisoformat(terms['first_payment'])
    if day < first:
        return 0
    frequency = terms['frequency']
    if frequency in ('weekly', 'biweekly'):
        return (day - first).days // (7 if frequency == 'weekly' else 14) + 1
    # Use the original payment day, including its shorter-month adjustment.
    months = (day.year - first.year) * 12 + day.month - first.month
    candidate = months // (12 // PER_YEAR[frequency]) + 1
    return candidate - 1 if payment_date(terms, candidate) > day else candidate


def payment_date(terms, number):
    first = date.fromisoformat(terms['first_payment'])
    frequency = terms['frequency']
    if frequency in ('weekly', 'biweekly'):
        return first + timedelta(weeks=(number - 1) * (2 if frequency == 'biweekly' else 1))
    return first + relativedelta(months=(number - 1) * (12 // PER_YEAR[frequency]))


def terms_for_payment(raw, amount, day):
    terms = validate_terms(raw)
    if terms is not None:
        if amount is None or not isfinite(amount) or amount <= 0 or day is None:
            raise ValueError('Payment amount and date are required')
        if not 1 <= payment_number(terms, day) <= payment_count(terms):
            raise ValueError('Payment outside loan term')
    return terms


def next_payment_on_or_after(terms, day):
    number = max(1, payment_number(terms, day))
    due = payment_date(terms, number)
    if due < day:
        due = payment_date(terms, number + 1)
    return due


def submitted_terms(form, amount, day, frequency=None):
    if form.get('category') != 'loan_payment' or form.get('track_interest') != 'on':
        return None
    return terms_for_payment({
        'annual_rate': form.get('annual_rate'), 'term': form.get('loan_term'),
        'term_unit': form.get('term_unit'),
        'first_payment': form.get('start_date') if frequency else form.get('first_payment'),
        'frequency': frequency or form.get('loan_frequency'),
    }, amount, day)


def estimate(terms, amount, day):
    """Split the dated payment and estimate interest across the original term."""
    if not terms or amount is None or day is None:
        return None
    count = payment_count(terms)
    period = payment_number(terms, day)
    if not 1 <= period <= count:
        return None
    with localcontext() as ctx:
        ctx.prec = 50
        payment = Decimal(str(amount))
        rate = Decimal(str(terms['annual_rate'])) / (100 * PER_YEAR[terms['frequency']])
        # Preserve cents even for a nearly zero rate in the annuity subtraction.
        ctx.prec = max(ctx.prec, payment.adjusted() + max(0, -rate.adjusted()) + 14)
        if rate:
            discount = 1 / (1 + rate)
            interest = payment * (1 - discount ** (count - period + 1))
            financed = payment * (1 - discount ** count) / rate
        else:
            interest = Decimal(0)
            financed = payment * count
        return {
            'interest': round_money(interest), 'principal': round_money(payment) - round_money(interest),
            'financed': round_money(financed), 'total_interest': round_money(payment * count - financed),
            'count': count,
        }


def round_money(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)
