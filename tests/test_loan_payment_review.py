from datetime import date, timedelta
import re

import pytest

from app import db
from app.models import Expense, RecurringExpense
from app.services.expense_breakdown import category_breakdown


@pytest.mark.parametrize('action,expected', [('add', 1), ('skip', 0)])
def test_history_is_explicit_and_repeat_submit_safe(auth_client, sample_vehicle, action, expected):
    first = date.today() - timedelta(days=29)
    response = auth_client.post('/recurring/new', data={
        'vehicle_id': sample_vehicle.id, 'category': 'loan_payment', 'frequency': 'biweekly',
        'amount': '125', 'name': 'Test loan', 'start_date': first.isoformat(),
    })
    schedule = RecurringExpense.query.one()
    url = f'/recurring/{schedule.id}/history'
    assert response.location.endswith(url)
    page = auth_client.get(url).text
    assert page.count('name="payment_date"') == 3
    version = re.search(r'name="version" value="([^"]+)', page)[1]
    assert Expense.query.count() == 0
    for _ in range(2):
        auth_client.post(url, data={'action': action, 'version': version, 'payment_date': first.isoformat()})
    assert Expense.query.count() == expected
    assert schedule.next_due == first + timedelta(days=42)
    assert schedule.history_reviewed_on == date.today()


def test_breakdown_includes_both_tracked_and_untracked(auth_client, test_user, sample_vehicle):
    common = dict(vehicle_id=sample_vehicle.id, user_id=test_user.id, category='loan_payment',
                  description='Bank', date=date(2027, 1, 31), cost=100)
    db.session.add(Expense(**common))
    db.session.add(Expense(**common, loan_terms={
        'term': 2, 'term_unit': 'payments', 'annual_rate': 12, 'frequency': 'monthly',
        'first_payment': '2027-01-31'}))
    db.session.commit()
    amounts = {row['key']: row['total'] for row in category_breakdown(sample_vehicle.expenses)}
    assert amounts == {'loan_payment': 100, 'loan_principal': 98.03, 'loan_interest': 1.97}
    for endpoint in ('/dashboard', f'/vehicles/{sample_vehicle.id}', '/expenses/'):
        page = auth_client.get(endpoint)
        assert page.status_code == 200 and 'Loan principal' in page.text and 'Estimated loan interest' in page.text
    assert sample_vehicle.get_total_expense_cost() == 200


def test_history_checks_existing_expenses_and_splits_selected_interest(auth_client, sample_vehicle, test_user):
    first = date.today() - timedelta(days=29)
    data = {'vehicle_id': sample_vehicle.id, 'category': 'loan_payment', 'frequency': 'biweekly',
            'amount': '100', 'name': 'Bank', 'start_date': first.isoformat(), 'track_interest': 'on',
            'annual_rate': '6', 'loan_term': '130', 'term_unit': 'payments'}
    common = dict(vehicle_id=sample_vehicle.id, user_id=test_user.id, category='loan_payment', cost=100)
    db.session.add(Expense(**common, date=first, description='Bank (auto-generated)'))
    db.session.add(Expense(**common, date=first + timedelta(days=14), description='Manual payment'))
    db.session.commit()
    response = auth_client.post('/recurring/new', data=data)
    url = response.location
    page = auth_client.get(url).text
    assert f'name="payment_date" value="{first.isoformat()}"' not in page
    assert f'value="{first + timedelta(days=14)}" checked' not in page
    version = re.search(r'name="version" value="([^"]+)', page)[1]
    selected = first + timedelta(days=28)
    auth_client.post(url, data={'action': 'add', 'version': version, 'payment_date': selected.isoformat()})
    added = Expense.query.filter_by(date=selected).one()
    assert added.cost == 100
    assert added.loan_estimate['interest'] > 0
    assert Expense.query.count() == 3
