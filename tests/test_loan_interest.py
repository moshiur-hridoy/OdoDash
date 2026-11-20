from datetime import date
from decimal import Decimal
import pytest

from app import db
from app.models import Expense, RecurringExpense
from app.services.loan_interest import estimate, terms_for_payment
from app.services.recurring_processor import generate_expense_for_period


def terms(**changes):
    return dict({'annual_rate': 12, 'frequency': 'monthly', 'term': 2,
                 'term_unit': 'payments', 'first_payment': '2027-01-31'}, **changes)


def test_month_end_and_closed_form():
    loan = terms()
    # Independently discount two payments of 100 at 1% per period.
    owed = Decimal('100') / Decimal('1.01') + Decimal('100') / Decimal('1.01') ** 2
    first = estimate(loan, 100, date(2027, 1, 31))
    assert first['financed'] == owed.quantize(Decimal('.01'))
    assert first['interest'] == Decimal('1.97') and first['principal'] == Decimal('98.03')
    assert first['total_interest'] == Decimal('2.96')
    assert estimate(loan, 100, date(2027, 2, 28))['interest'] == Decimal('0.99')
    assert estimate(terms(annual_rate=0), 100, date(2027, 2, 28))['interest'] == 0


@pytest.mark.parametrize('invalid', [
    {'annual_rate': 'nan'}, {'annual_rate': -1}, {'term': 0},
    {'frequency': 'bad'}, {'first_payment': 'not a date'}, {'term_unit': 'bad'},
])
def test_invalid_loan_terms(invalid):
    with pytest.raises(ValueError):
        terms_for_payment(terms(**invalid), 100, date(2027, 1, 31))


def test_recurring_interest_is_optional_and_stops_at_payoff(auth_client, sample_vehicle, monkeypatch):
    class BeforeFirstPayment(date):
        @classmethod
        def today(cls):
            return cls(2026, 12, 23)

    monkeypatch.setattr('app.routes.recurring.date', BeforeFirstPayment)
    data = {'name': 'Loan', 'vehicle_id': sample_vehicle.id, 'category': 'loan_payment',
            'start_date': '2026-12-24', 'frequency': 'biweekly', 'amount': '125',
            'annual_rate': '6', 'loan_term': '2', 'term_unit': 'payments'}
    auth_client.post('/recurring/new', data=data)
    plain = RecurringExpense.query.one()
    assert plain.loan_terms is None
    data.update(name='Tracked', track_interest='on')
    auth_client.post('/recurring/new', data=data)
    schedule = RecurringExpense.query.filter_by(name='Tracked').one()
    first = generate_expense_for_period(schedule)
    assert schedule.next_due == date(2027, 1, 7)
    assert first.cost == 125 and first.loan_estimate['interest'] == Decimal('0.57')
    last = generate_expense_for_period(schedule)
    assert last.loan_estimate['interest'] == Decimal('0.29')
    assert schedule.next_due is None and not schedule.is_active
    assert generate_expense_for_period(schedule) is None
    db.session.commit()
    assert Expense.query.count() == 2
    assert sample_vehicle.get_total_expense_cost() == 250
    assert '0.86' in auth_client.get(f'/vehicles/{sample_vehicle.id}').text


def test_one_time_and_changing_category(auth_client, sample_vehicle):
    data = {'vehicle_id': sample_vehicle.id, 'category': 'loan_payment', 'description': 'Car loan',
            'date': '2027-01-31', 'cost': '100', 'track_interest': 'on', 'annual_rate': '12',
            'loan_term': '2', 'term_unit': 'months', 'first_payment': '2027-01-31',
            'loan_frequency': 'monthly'}
    auth_client.post('/expenses/new', data=dict(data, annual_rate='bad'))
    assert not Expense.query.count()
    auth_client.post('/expenses/new', data=data)
    expense = Expense.query.one()
    assert expense.loan_estimate['interest'] == Decimal('1.97')
    assert '1.97' in auth_client.get(f'/expenses/{expense.id}/edit').text
    auth_client.post(f'/expenses/{expense.id}/edit', data=dict(data, category='other'))
    assert expense.loan_terms is None and expense.cost == 100


def test_months_term_biweekly_and_midloan_entry():
    loan = terms(term=60, term_unit='months', frequency='biweekly', first_payment='2026-01-01')
    first = estimate(loan, 250, date(2026, 1, 1))
    later = estimate(loan, 250, date(2026, 12, 31))
    assert first['count'] == 130 and later['interest'] < first['interest']
    assert later['interest'] + later['principal'] == Decimal('250.00')


def test_api_and_export_preserve_terms(client, api_headers, sample_vehicle, auth_client):
    import csv
    import io
    import zipfile
    payload = {'date': '2027-01-31', 'cost': 100, 'description': 'Instalment',
               'category': 'loan_payment', 'loan_terms': terms()}
    result = client.post(f'/api/v1/vehicles/{sample_vehicle.id}/expenses', headers=api_headers, json=payload)
    assert result.status_code == 201 and result.json['loan_terms'] == terms()
    url = f"/api/v1/expenses/{result.json['id']}"
    assert client.patch(url, headers=api_headers, json={'date': '2026-01-01'}).status_code == 400
    assert client.get(url, headers=api_headers).json['date'] == '2027-01-31'
    with zipfile.ZipFile(io.BytesIO(auth_client.get('/api/export/csv').data)) as archive:
        row = next(csv.DictReader(io.StringIO(archive.read('expenses.csv').decode())))
        assert (row['estimated_interest'], row['estimated_principal']) == ('1.97', '98.03')
    assert auth_client.get('/api/export/json').json['vehicles'][0]['expenses'][0]['loan_terms'] == terms()
    assert client.patch(url, headers=api_headers, json={'category': 'other'}).json['loan_terms'] is None


def test_start_tracking_existing_loan_without_repeating_date(auth_client, sample_vehicle):
    from datetime import timedelta
    first = date.today() - timedelta(days=29)
    data = {'name': 'Existing loan', 'vehicle_id': sample_vehicle.id, 'category': 'loan_payment',
            'frequency': 'biweekly', 'amount': '125', 'track_interest': 'on', 'annual_rate': '6',
            'loan_term': '60', 'term_unit': 'months', 'start_date': first.isoformat()}
    auth_client.post('/recurring/new', data=data)
    schedule = RecurringExpense.query.one()
    assert schedule.start_date == first
    assert schedule.next_due == first + timedelta(days=42)
    assert schedule.loan_terms['first_payment'] == first.isoformat()
    assert Expense.query.count() == 0


def test_saved_splits_survive_loan_changes_and_restore(auth_client, sample_vehicle, test_user, admin_user):
    from app.services.backup_restore import restore_backup
    schedule = RecurringExpense(vehicle_id=sample_vehicle.id, user_id=test_user.id,
                                name='Fixed loan', category='loan_payment', amount=100,
                                frequency='monthly', start_date=date(2027, 1, 31),
                                next_due=date(2027, 1, 31), loan_terms=terms(), is_active=True)
    db.session.add(schedule)
    entry = generate_expense_for_period(schedule)
    db.session.commit()
    schedule.loan_terms = None
    db.session.commit()
    assert entry.loan_estimate['interest'] == Decimal('1.97')
    backup = auth_client.get('/api/export/json').json
    restore_backup(backup, admin_user)
    restored = Expense.query.filter_by(user_id=admin_user.id).one()
    assert restored.loan_estimate['interest'] == Decimal('1.97')


def test_recurring_form_has_one_start_date_and_preserves_legacy_origin(auth_client, sample_vehicle, test_user):
    schedule = RecurringExpense(vehicle_id=sample_vehicle.id, user_id=test_user.id,
                                name='Existing', category='loan_payment', amount=100,
                                frequency='monthly', start_date=date(2027, 2, 28),
                                next_due=date(2027, 2, 28), loan_terms=terms())
    db.session.add(schedule)
    db.session.commit()
    url = f'/recurring/{schedule.id}/edit'
    page = auth_client.get(url).text
    assert 'name="first_payment"' not in page
    assert 'value="2027-01-31"' in page
    auth_client.post(url, data={'name': 'Existing', 'category': 'loan_payment', 'frequency': 'monthly',
                               'amount': '100', 'start_date': '2027-01-31', 'next_due': '2027-02-28',
                               'track_interest': 'on', 'annual_rate': '12', 'loan_term': '2',
                               'term_unit': 'payments'})
    db.session.refresh(schedule)
    assert schedule.start_date.isoformat() == schedule.loan_terms['first_payment'] == '2027-01-31'
    assert schedule.next_due == date(2027, 2, 28)
    assert schedule.loan_estimate['interest'] == Decimal('0.99')


@pytest.mark.parametrize('endpoint', ['/expenses/loan-estimate', '/recurring/loan-estimate'])
def test_live_preview_recalculates_without_creating_expenses(auth_client, endpoint):
    fields = dict(amount='100', frequency='monthly', annual_rate='12', loan_term='2',
                  term_unit='payments', first_payment='2027-01-31', payment_date='2027-02-28')
    assert auth_client.post(endpoint, data=fields).json == {
        'interest': '0.99', 'financed': '197.04', 'total_interest': '2.96'}
    fields.update(annual_rate='0', amount='125')
    assert auth_client.post(endpoint, data=fields).json == {
        'interest': '0.00', 'financed': '250.00', 'total_interest': '0.00'}
    fields.update(first_payment='', payment_date='')
    assert auth_client.post(endpoint, data=fields).json == {'financed': '250.00', 'total_interest': '0.00'}
    fields.update(loan_term='')
    assert auth_client.post(endpoint, data=fields).json == {}
    assert Expense.query.count() == RecurringExpense.query.count() == 0
