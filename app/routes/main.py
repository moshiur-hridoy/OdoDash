from flask import Blueprint, render_template, redirect, request, url_for, send_from_directory, current_app
from flask_login import login_required, current_user
from flask_babel import gettext
from datetime import datetime, timedelta
from sqlalchemy import func
from app import db
from app.models import Vehicle, FuelLog, Expense, ChargingSession, FuelPriceHistory, FuelStation, MileageAllowance, Attachment, Reminder, Note, EXPENSE_CATEGORIES
from app.utils import shared_reading_unit

bp = Blueprint('main', __name__)

#: "Needs attention" lists reminders overdue or due within this many days.
ATTENTION_DAYS = 30
#: How many of them the card lists; the count and "View all" cover the rest.
#: Four keeps the card about as tall as the hero beside it.
ATTENTION_SHOWN = 4
#: Station prices older than this do not count towards "Cheapest Fuel".
PRICE_WINDOW_DAYS = 60


@bp.route('/')
def index():
    if current_user.is_authenticated:
        # Redirect to user's configured start page
        start_page = current_user.start_page or 'dashboard'
        page_routes = {
            'dashboard': 'main.dashboard',
            'vehicles': 'vehicles.index',
            'fuel': 'fuel.index',
            'fuel_quick': 'fuel.quick',
            'expenses': 'expenses.index',
            'reminders': 'reminders.index',
            'maintenance': 'maintenance.index',
            'recurring': 'recurring.index',
            'documents': 'documents.index',
            'stations': 'stations.index',
            'trips': 'trips.index',
            'charging': 'charging.index',
            'notes': 'notes.index',
            'allowance': 'allowance.index',
        }
        route = page_routes.get(start_page, 'main.dashboard')
        return redirect(url_for(route))
    return redirect(url_for('auth.login'))


@bp.route('/offline')
def offline():
    """Offline page for PWA"""
    return render_template('offline.html')


@bp.route('/sw.js')
def service_worker():
    """Serve service worker from root URL for proper scope"""
    return send_from_directory(
        current_app.static_folder, 'sw.js',
        mimetype='application/javascript'
    )


@bp.route('/dashboard')
@login_required
def dashboard():
    vehicles = current_user.get_all_vehicles()
    vehicle_ids = [v.id for v in vehicles]
    period = 'year' if request.args.get('period') == 'year' else 'month'
    now = datetime.now()

    # All-time totals
    total_fuel_cost = _sum(FuelLog.total_cost, FuelLog, vehicle_ids)
    total_expense_cost = _sum(Expense.cost, Expense, vehicle_ids)
    total_charging_cost = _sum(ChargingSession.total_cost, ChargingSession, vehicle_ids)
    # Total mileage allowance received (#208) — offsets running costs
    total_allowance = _sum(MileageAllowance.amount, MileageAllowance, vehicle_ids)

    # Total distance (uses user's distance_unit for Tessie conversion; raw logs are in their stored unit)
    total_distance = sum(v.get_total_distance(current_user.distance_unit) for v in vehicles)

    total_cost = total_fuel_cost + total_expense_cost + total_charging_cost
    net_cost = total_cost - total_allowance
    cost_per_distance = total_cost / total_distance if total_distance > 0 else None

    # The hero figure: spending in the current month or year, split into fuel,
    # charging and everything else, set against the same stretch of the one
    # before it. Comparing twelve days of November with all of October would
    # read as a fall every month until the last week, so the previous period
    # is cut off at the same point.
    if period == 'year':
        current_start = datetime(now.year, 1, 1)
        current_end = datetime(now.year + 1, 1, 1)
        previous_start = datetime(now.year - 1, 1, 1)
    else:
        current_start = datetime(now.year, now.month, 1)
        current_end = _add_months(current_start, 1)
        previous_start = _add_months(current_start, -1)
    current_split = _spending_between(vehicle_ids, current_start, current_end)
    previous_cutoff = _same_point_before(now, period, previous_start, current_start)
    previous_total = sum(_spending_between(vehicle_ids, previous_start, previous_cutoff).values())
    period_total = sum(current_split.values())
    period_change = None
    if previous_total > 0:
        period_change = round((period_total - previous_total) / previous_total * 100)

    # Month by month under the hero figure: the last six months, or this
    # year's months so far. Whole months, so the current one is partial.
    if period == 'year':
        bar_months = [datetime(now.year, m, 1) for m in range(1, now.month + 1)]
    else:
        bar_months = [_add_months(current_start, -i) for i in range(5, -1, -1)]
    month_totals = [(m, sum(_spending_between(vehicle_ids, m, _add_months(m, 1)).values()))
                    for m in bar_months]

    # Year to date, and where it is heading at the same pace.
    year_start = datetime(now.year, 1, 1)
    year_to_date = (period_total if period == 'year'
                    else sum(_spending_between(vehicle_ids, year_start, datetime(now.year + 1, 1, 1)).values()))
    days_in_year = (datetime(now.year + 1, 1, 1) - year_start).days
    year_projection = year_to_date / now.timetuple().tm_yday * days_in_year if year_to_date else None
    month_average = year_to_date / now.month

    # Expenses grouped by category for the dashboard chart (#145),
    # with labels translated server-side
    expenses_by_category = {}
    if vehicle_ids:
        category_rows = db.session.query(
            Expense.category, func.sum(Expense.cost)
        ).filter(
            Expense.vehicle_id.in_(vehicle_ids)
        ).group_by(Expense.category).all()
        expenses_by_category = {
            str(dict(EXPENSE_CATEGORIES).get(cat, (cat or '').capitalize())): round(total, 2)
            for cat, total in category_rows if total
        }

        if total_fuel_cost:
            label = str(gettext('Fuel'))
            expenses_by_category[label] = round(expenses_by_category.get(label, 0) + total_fuel_cost, 2)
        if total_charging_cost:
            label = str(gettext('Charging'))
            expenses_by_category[label] = round(expenses_by_category.get(label, 0) + total_charging_cost, 2)

    show_stations = current_user.show_menu_stations is None or current_user.show_menu_stations
    cheapest_price = _cheapest_price(current_user.id) if vehicle_ids and show_stations else None

    # Open reminders, overdue first then soonest. "Needs attention" takes the
    # ones overdue or due within ATTENTION_DAYS: an inspection eight months
    # out is not something to act on today. All of them still set each
    # vehicle's status. Latest notes alongside.
    dashboard_reminders = []
    dashboard_reminders_total = 0
    open_reminders_total = 0
    dashboard_notes = []
    soonest_due = {}
    if vehicle_ids:
        open_reminders = Reminder.query.filter(
            Reminder.vehicle_id.in_(vehicle_ids),
            Reminder.is_completed.is_(False)
        ).order_by(Reminder.due_date).all()
        open_reminders_total = len(open_reminders)
        attention_due = [r for r in open_reminders if r.days_until_due() <= ATTENTION_DAYS]
        dashboard_reminders_total = len(attention_due)
        dashboard_reminders = attention_due[:ATTENTION_SHOWN]
        for reminder in open_reminders:
            soonest_due.setdefault(reminder.vehicle_id, reminder.days_until_due())
        dashboard_notes = Note.query.filter(
            Note.vehicle_id.in_(vehicle_ids)
        ).order_by(Note.date.desc(), Note.id.desc()).limit(5).all()

    vehicle_rows = [_vehicle_row(v, soonest_due.get(v.id)) for v in vehicles]

    # Recent activity: fuel, charging and expenses in one list, newest first.
    recent_activity = []
    if vehicle_ids:
        for log in FuelLog.query.filter(FuelLog.vehicle_id.in_(vehicle_ids)).order_by(
                FuelLog.date.desc(), FuelLog.odometer.desc()).limit(6):
            recent_activity.append({'kind': 'fuel', 'date': log.date, 'vehicle': log.vehicle,
                                    'odometer': log.odometer, 'amount': log.total_cost or 0, 'entry': log})
        for charge in ChargingSession.query.filter(ChargingSession.vehicle_id.in_(vehicle_ids)).order_by(
                ChargingSession.date.desc()).limit(6):
            recent_activity.append({'kind': 'charging', 'date': charge.date, 'vehicle': charge.vehicle,
                                    'odometer': charge.odometer, 'amount': charge.total_cost or 0, 'entry': charge})
        for expense in Expense.query.filter(Expense.vehicle_id.in_(vehicle_ids)).order_by(
                Expense.date.desc()).limit(6):
            recent_activity.append({'kind': 'expense', 'date': expense.date, 'vehicle': expense.vehicle,
                                    'odometer': expense.odometer, 'amount': expense.cost or 0, 'entry': expense,
                                    'label': str(dict(EXPENSE_CATEGORIES).get(
                                        expense.category, (expense.category or '').capitalize()))})
        recent_activity.sort(key=lambda row: _as_datetime(row['date']), reverse=True)
        recent_activity = recent_activity[:6]

    # A fleet total is only honest while every vehicle meters the same way.
    # One hours-metered machine among the cars and the sum mixes engine hours
    # with distance, so the template says so rather than labelling it with a
    # distance unit (#324).
    total_distance_unit = (shared_reading_unit(vehicles, current_user.distance_unit)
                           if vehicles else current_user.distance_unit)

    return render_template('dashboard.html',
                           period=period,
                           today=now,
                           period_start=current_start,
                           period_total=period_total,
                           period_split=current_split,
                           period_change=period_change,
                           previous_total=previous_total,
                           month_totals=month_totals,
                           year_to_date=year_to_date,
                           year_projection=year_projection,
                           month_average=month_average,
                           total_distance_unit=total_distance_unit,
                           vehicles=vehicles,
                           vehicle_rows=vehicle_rows,
                           total_fuel_cost=total_fuel_cost,
                           total_expense_cost=total_expense_cost,
                           total_charging_cost=total_charging_cost,
                           total_allowance=total_allowance,
                           net_cost=net_cost,
                           total_cost=total_cost,
                           expenses_by_category=expenses_by_category,
                           total_distance=total_distance,
                           cost_per_distance=cost_per_distance,
                           recent_activity=recent_activity,
                           cheapest_price=cheapest_price,
                           dashboard_reminders=dashboard_reminders,
                           dashboard_reminders_total=dashboard_reminders_total,
                           open_reminders_total=open_reminders_total,
                           attention_days=ATTENTION_DAYS,
                           dashboard_notes=dashboard_notes)


def _sum(column, model, vehicle_ids, start=None, end=None):
    """Sum ``column`` over the given vehicles, optionally within [start, end)."""
    if not vehicle_ids:
        return 0
    query = db.session.query(func.sum(column)).filter(model.vehicle_id.in_(vehicle_ids))
    if start is not None:
        # The date columns are db.Date. SQLite compares them as text, so a
        # datetime bound ('2026-11-01 00:00:00') would sort after the first
        # day of the month ('2026-11-01') and drop that day's entries.
        query = query.filter(model.date >= start.date(), model.date < end.date())
    return query.scalar() or 0


def _spending_between(vehicle_ids, start, end):
    """Fuel, charging and other spending in [start, end)."""
    return {
        'fuel': _sum(FuelLog.total_cost, FuelLog, vehicle_ids, start, end),
        'charging': _sum(ChargingSession.total_cost, ChargingSession, vehicle_ids, start, end),
        'other': _sum(Expense.cost, Expense, vehicle_ids, start, end),
    }


def _add_months(moment, months):
    """The first of the month ``months`` away from ``moment``'s month."""
    index = moment.year * 12 + moment.month - 1 + months
    return datetime(index // 12, index % 12 + 1, 1)


def _as_datetime(value):
    """Dates and datetimes, comparable with each other for sorting."""
    if isinstance(value, datetime):
        return value
    return datetime(value.year, value.month, value.day)


def _same_point_before(now, period, previous_start, current_start):
    """End (exclusive) of the previous period cut off where this one is now.

    Today counts in full, so on 12 November the month compares 1-12 November
    with 1-12 October. A day the previous month does not have (31 March
    against February) takes the whole of it.
    """
    if period == 'year':
        try:
            same_day = now.replace(year=now.year - 1)
        except ValueError:  # 29 February
            same_day = now.replace(year=now.year - 1, day=28)
        cutoff = datetime(same_day.year, same_day.month, same_day.day) + timedelta(days=1)
    else:
        cutoff = previous_start + timedelta(days=now.day)
    return min(cutoff, current_start)


def _cheapest_price(user_id):
    """The cheapest recent price, when the user's stations disagree on price.

    Takes each station's latest price per fuel within PRICE_WINDOW_DAYS. It
    returns None unless at least two stations quote different prices for one
    fuel: with a single station, or with prices set by the state (Bangladesh,
    among others) and so the same everywhere, "cheapest" means nothing. With
    several such fuels, the one most stations report wins.
    """
    since = datetime.now().date() - timedelta(days=PRICE_WINDOW_DAYS)
    latest = db.session.query(
        FuelPriceHistory.station_id,
        FuelPriceHistory.fuel_type,
        func.max(FuelPriceHistory.date).label('max_date'),
    ).filter(
        FuelPriceHistory.user_id == user_id,
        FuelPriceHistory.date >= since,
    ).group_by(FuelPriceHistory.station_id, FuelPriceHistory.fuel_type).subquery()
    rows = db.session.query(FuelPriceHistory).join(
        latest,
        db.and_(
            FuelPriceHistory.station_id == latest.c.station_id,
            FuelPriceHistory.fuel_type == latest.c.fuel_type,
            FuelPriceHistory.date == latest.c.max_date,
        ),
    ).filter(FuelPriceHistory.user_id == user_id).order_by(FuelPriceHistory.id).all()

    by_fuel = {}
    for row in rows:
        # Two entries on a station's latest day: the later one stands.
        by_fuel.setdefault(row.fuel_type, {})[row.station_id] = row
    candidates = []
    for fuel_type, per_station in by_fuel.items():
        prices = [r.price_per_unit for r in per_station.values()]
        if len(per_station) >= 2 and max(prices) - min(prices) > 1e-9:
            candidates.append((-len(per_station), fuel_type, per_station))
    if not candidates:
        return None
    _, _, per_station = min(candidates, key=lambda c: (c[0], c[1]))
    return min(per_station.values(), key=lambda r: r.price_per_unit)


def _vehicle_row(vehicle, soonest_due):
    """What the dashboard's vehicle list shows for one vehicle."""
    if vehicle.fuel_type == 'electric':
        consumption = vehicle.get_average_charging_consumption()
        consumption_unit = f'kWh/100 {vehicle.get_reading_unit()}'
    else:
        consumption = vehicle.get_average_consumption(current_user.consumption_unit, current_user.volume_unit)
        consumption_unit = vehicle.get_consumption_unit() or current_user.consumption_unit
    if soonest_due is None or soonest_due > 7:
        status = 'ok'
    elif soonest_due < 0:
        status = 'overdue'
    else:
        status = 'soon'
    return {
        'vehicle': vehicle,
        'odometer': vehicle.get_last_odometer(vehicle.get_effective_odometer_unit()),
        'reading_unit': vehicle.get_reading_unit(),
        'consumption': consumption,
        'consumption_unit': consumption_unit,
        'status': status,
    }


@bp.route('/timeline/<int:vehicle_id>')
@login_required
def timeline(vehicle_id):
    """Service timeline showing maintenance history and expenses"""
    vehicles = current_user.get_all_vehicles()
    vehicle = db.get_or_404(Vehicle, vehicle_id)

    if vehicle not in vehicles:
        return redirect(url_for('main.dashboard'))

    # Get all fuel logs, expenses, and charging sessions for timeline
    fuel_logs = vehicle.fuel_logs.order_by(FuelLog.date.desc(), FuelLog.odometer.desc()).all()
    expenses = vehicle.expenses.order_by(Expense.date.desc()).all()
    charging_sessions = vehicle.charging_sessions.order_by(ChargingSession.date.desc()).all()

    # Attachments for this vehicle's fuel logs and expenses, fetched in two
    # grouped queries so the timeline doesn't issue a query per event (#284).
    # Joining through the parent keeps the filter on vehicle_id rather than a
    # long IN list of entry ids.
    fuel_attachments = {}
    for attachment in Attachment.query.join(
            FuelLog, Attachment.fuel_log_id == FuelLog.id).filter(
            FuelLog.vehicle_id == vehicle_id).all():
        fuel_attachments.setdefault(attachment.fuel_log_id, []).append(attachment)

    expense_attachments = {}
    for attachment in Attachment.query.join(
            Expense, Attachment.expense_id == Expense.id).filter(
            Expense.vehicle_id == vehicle_id).all():
        expense_attachments.setdefault(attachment.expense_id, []).append(attachment)

    # Combine into timeline events
    timeline_events = []

    for log in fuel_logs:
        timeline_events.append({
            'date': log.date,
            'type': 'fuel',
            'title': (gettext('Fuel: %(volume).1f L', volume=log.volume)
                      if log.volume else gettext('Fuel Log')),
            'description': log.station or '',
            'cost': log.total_cost or 0,
            'odometer': log.odometer,
            'notes': log.notes,
            'attachments': fuel_attachments.get(log.id, [])
        })

    for expense in expenses:
        timeline_events.append({
            'date': expense.date,
            'type': 'expense',
            'title': expense.description,
            'description': str(dict(EXPENSE_CATEGORIES).get(expense.category, expense.category.capitalize())),
            'cost': expense.cost or 0,
            'odometer': expense.odometer,
            'notes': expense.notes,
            'attachments': expense_attachments.get(expense.id, [])
        })

    for session in charging_sessions:
        timeline_events.append({
            'date': session.date,
            'type': 'charging',
            'title': (gettext('Charging: %(kwh).1f kWh', kwh=session.kwh_added)
                      if session.kwh_added else gettext('Charging Session')),
            'description': session.location or '',
            'cost': session.total_cost or 0,
            'odometer': session.odometer,
            'notes': session.notes,
            'attachments': []
        })

    # Sort by date descending
    timeline_events.sort(key=lambda x: x['date'], reverse=True)

    # Prepare chart data - monthly costs for the last 12 calendar months.
    # Walk real calendar months rather than 30-day steps: fixed-size steps
    # drift against month boundaries, duplicating some months and skipping
    # others in the chart (#270).
    chart_data = {'labels': [], 'fuel': [], 'expenses': [], 'charging': []}
    today = datetime.now()
    months = []
    year, month = today.year, today.month
    for _ in range(12):
        months.append((year, month))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    for year, month in reversed(months):
        month_start = datetime(year, month, 1)
        if month == 12:
            month_end = datetime(year + 1, 1, 1)
        else:
            month_end = datetime(year, month + 1, 1)

        chart_data['labels'].append(month_start.strftime('%b %Y'))

        fuel_cost = db.session.query(func.sum(FuelLog.total_cost)).filter(
            FuelLog.vehicle_id == vehicle_id,
            FuelLog.date >= month_start,
            FuelLog.date < month_end
        ).scalar() or 0

        expense_cost = db.session.query(func.sum(Expense.cost)).filter(
            Expense.vehicle_id == vehicle_id,
            Expense.date >= month_start,
            Expense.date < month_end
        ).scalar() or 0

        charging_cost = db.session.query(func.sum(ChargingSession.total_cost)).filter(
            ChargingSession.vehicle_id == vehicle_id,
            ChargingSession.date >= month_start,
            ChargingSession.date < month_end
        ).scalar() or 0

        chart_data['fuel'].append(round(fuel_cost, 2))
        chart_data['expenses'].append(round(expense_cost, 2))
        chart_data['charging'].append(round(charging_cost, 2))

    return render_template('timeline/index.html',
                           vehicle=vehicle,
                           timeline_events=timeline_events,
                           chart_data=chart_data)
