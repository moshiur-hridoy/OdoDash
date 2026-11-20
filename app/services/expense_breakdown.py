"""Allocate recorded spending to chart categories without creating extra expenses."""
from collections import Counter
from decimal import Decimal

from flask_babel import gettext as _
from sqlalchemy import func

from app.models import Expense, EXPENSE_CATEGORIES


def category_breakdown(query):
    totals, counts = Counter(), Counter()
    for key, total, count in query.with_entities(
            Expense.category, func.sum(Expense.cost), func.count(Expense.id)).group_by(Expense.category):
        totals[key] = Decimal(str(total or 0))
        counts[key] = count
    if counts['loan_payment']:
        tracked = query.filter(Expense.category == 'loan_payment', Expense.loan_terms.isnot(None))
        for expense in tracked:
            split = expense.loan_estimate
            if split is None:
                continue
            totals['loan_payment'] -= Decimal(str(expense.cost))
            counts['loan_payment'] -= 1
            for key in ('principal', 'interest'):
                totals['loan_' + key] += split[key]
                counts['loan_' + key] += 1
    labels = dict(EXPENSE_CATEGORIES)
    labels.update(loan_principal=_('Loan principal'), loan_interest=_('Estimated loan interest'))
    return [
        {'key': key, 'label': str(labels.get(key, key)), 'total': float(round(total, 2)),
         'count': counts[key]}
        for key, total in totals.most_common() if counts[key]
    ]
