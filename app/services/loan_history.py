"""Review earlier instalments without advancing the schedule while posting them."""
from datetime import date

from app.models import Expense
from app.services.loan_interest import payment_count, payment_date


def loan_history(schedule, today):
    terms = schedule.loan_terms or {
        'first_payment': schedule.start_date.isoformat(), 'frequency': schedule.frequency,
    }
    first = date.fromisoformat(terms['first_payment'])
    entries = Expense.query.filter(
        Expense.vehicle_id == schedule.vehicle_id, Expense.category == 'loan_payment',
        Expense.date >= first, Expense.date <= today,
    ).order_by(Expense.date, Expense.id).all()
    generated = {entry.date for entry in entries
                 if entry.description == f'{schedule.name} (auto-generated)'}
    possible = {entry.date for entry in entries if entry.cost == schedule.amount}
    candidates = []
    limit = payment_count(terms) if schedule.loan_terms else None
    number = 1
    while limit is None or number <= limit:
        due = payment_date(terms, number)
        if schedule.end_date and due > schedule.end_date:
            break
        if due >= today and (not schedule.last_generated or due > schedule.last_generated):
            return candidates, entries, due
        if due < today and due not in generated:
            candidates.append((due, due in possible))
        number += 1
    return candidates, entries, None
