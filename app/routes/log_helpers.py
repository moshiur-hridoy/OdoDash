"""Shared helpers for the month-grouped log pages (fuel, charging, trips, notes)."""
from datetime import date

from sqlalchemy import extract, func

from app import db


def month_start(value):
    return date(value.year, value.month, 1)


def add_month(value):
    return date(value.year + value.month // 12, value.month % 12 + 1, 1)


def group_by_month(rows, date_of, totals=None):
    """Split already-sorted rows into [{month, total, rows}] blocks."""
    totals = totals or {}
    groups = []
    for row in rows:
        when = date_of(row)
        month = month_start(when) if when else None
        if not groups or groups[-1]['month'] != month:
            groups.append({'month': month, 'total': totals.get(month), 'rows': []})
        groups[-1]['rows'].append(row)
    return groups


def monthly_totals(model, column, vehicle_ids, months, *filters):
    """Sum of ``column`` per calendar month over every row, not just the page shown."""
    months = [m for m in months if m]
    if not months:
        return {}
    year = extract('year', model.date)
    month = extract('month', model.date)
    rows = (db.session.query(year, month, func.sum(column))
            .filter(model.vehicle_id.in_(vehicle_ids),
                    model.date >= min(months),
                    model.date < add_month(max(months)),
                    *filters)
            .group_by(year, month).all())
    return {date(int(y), int(m), 1): round(total or 0, 2) for y, m, total in rows}
