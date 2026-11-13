from datetime import date, datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from flask_babel import gettext as _
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from app import db
from app.utils import parse_decimal, utcnow
from app.models import Vehicle, ChargingSession, CHARGER_TYPES

bp = Blueprint('charging', __name__, url_prefix='/charging')


def parse_soc(raw):
    """Parse a state-of-charge percentage into an int (#390).

    Returns ``(value, error)``. Blank is valid (``None``). Decimals are
    rejected with a message instead of crashing or failing silently, because
    some mobile browsers skip native form validation.
    """
    raw = (raw or '').strip()
    if not raw:
        return None, None
    try:
        number = parse_decimal(raw)
    except (ValueError, TypeError):
        number = None
    error = _('State of charge must be a whole number between 0 and 100')
    try:
        if number is None or number != int(number) or not 0 <= int(number) <= 100:
            return None, error
    except (ValueError, OverflowError):
        return None, error
    return int(number), None


#: Sessions per page on the charging history.
SESSIONS_PER_PAGE = 50


def charging_log(vehicle_ids, page, per_page=SESSIONS_PER_PAGE):
    """One page of charging history plus its summary, for these vehicles.

    Shared by the charging page and the Charging tab of the fuel page, so the
    two always show the same figures.
    """
    from app.routes.log_helpers import month_start, group_by_month, monthly_totals

    now = utcnow()
    this_month = month_start(now)
    this_year = date(now.year, 1, 1)
    query = ChargingSession.query.filter(ChargingSession.vehicle_id.in_(vehicle_ids))

    # Newest first; same-day sessions by odometer (#329).
    pagination = query.options(joinedload(ChargingSession.vehicle)).order_by(
        ChargingSession.date.desc(), ChargingSession.odometer.desc(), ChargingSession.id.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    sessions = pagination.items
    totals = monthly_totals(ChargingSession, ChargingSession.total_cost, vehicle_ids,
                            [month_start(s.date) for s in sessions if s.date])

    def total(column, since):
        return db.session.query(func.sum(column)).filter(
            ChargingSession.vehicle_id.in_(vehicle_ids), ChargingSession.date >= since).scalar() or 0

    year_kwh = total(ChargingSession.kwh_added, this_year)
    year_cost = total(ChargingSession.total_cost, this_year)
    summary = {
        'month_cost': total(ChargingSession.total_cost, this_month),
        'month_kwh': total(ChargingSession.kwh_added, this_month),
        'year_cost': year_cost,
        'cost_per_kwh': (year_cost / year_kwh) if year_kwh and year_cost else None,
        'last': query.order_by(ChargingSession.date.desc(), ChargingSession.id.desc()).first(),
    }
    return dict(
        pagination=pagination,
        charging_sessions=sessions,
        groups=group_by_month(sessions, lambda s: s.date, totals),
        summary=summary,
        charger_types=dict(CHARGER_TYPES),
    )


@bp.route('/')
@login_required
def index():
    """Charging history: the same log as the fuel page's Charging tab."""
    vehicles = current_user.get_all_vehicles()
    # Vehicles that charge, plus any that already have sessions logged.
    charged = {vid for (vid,) in db.session.query(ChargingSession.vehicle_id).filter(
        ChargingSession.vehicle_id.in_([v.id for v in vehicles])).distinct()}
    ev_vehicles = [v for v in vehicles if v.is_electric() or v.id in charged]
    selected_vehicle = next((v for v in ev_vehicles if v.id == request.args.get('vehicle', type=int)), None)
    scope = [selected_vehicle] if selected_vehicle else ev_vehicles
    page = request.args.get('page', 1, type=int)

    log = charging_log([v.id for v in scope], page)
    return render_template('charging/index.html',
                           vehicles=ev_vehicles,
                           selected_vehicle=selected_vehicle,
                           charging_count=log['pagination'].total,
                           **log)


@bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    """Create a new charging session"""
    vehicles = current_user.get_all_vehicles()
    ev_vehicles = [v for v in vehicles if v.is_electric()]

    if not ev_vehicles:
        flash(_('No electric vehicles found. Add an EV or hybrid vehicle first.'), 'info')
        return redirect(url_for('vehicles.new'))

    if request.method == 'POST':
        vehicle_id = int(request.form.get('vehicle_id'))
        vehicle = db.get_or_404(Vehicle, vehicle_id)

        if vehicle not in vehicles:
            flash(_('Access denied'), 'error')
            return redirect(url_for('charging.index'))

        date_str = request.form.get('date')
        date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else datetime.now().date()

        start_time = None
        end_time = None
        if request.form.get('start_time'):
            start_time = datetime.strptime(request.form.get('start_time'), '%H:%M').time()
        if request.form.get('end_time'):
            end_time = datetime.strptime(request.form.get('end_time'), '%H:%M').time()

        start_soc, err = parse_soc(request.form.get('start_soc'))
        if err is None:
            end_soc, err = parse_soc(request.form.get('end_soc'))
        if err:
            flash(err, 'error')
            return redirect(url_for('charging.new'))

        session = ChargingSession(
            vehicle_id=vehicle_id,
            user_id=current_user.id,
            date=date,
            start_time=start_time,
            end_time=end_time,
            odometer=parse_decimal(request.form.get('odometer')) if request.form.get('odometer') else None,
            kwh_added=parse_decimal(request.form.get('kwh_added')) if request.form.get('kwh_added') else None,
            start_soc=start_soc,
            end_soc=end_soc,
            cost_per_kwh=parse_decimal(request.form.get('cost_per_kwh')) if request.form.get('cost_per_kwh') else None,
            total_cost=parse_decimal(request.form.get('total_cost')) if request.form.get('total_cost') else None,
            charger_type=request.form.get('charger_type'),
            location=request.form.get('location'),
            network=request.form.get('network'),
            notes=request.form.get('notes')
        )

        # Calculate total cost if not provided
        if session.kwh_added and session.cost_per_kwh and not session.total_cost:
            session.total_cost = round(session.kwh_added * session.cost_per_kwh, 2)

        db.session.add(session)
        db.session.commit()

        flash(_('Charging session logged successfully'), 'success')
        return redirect(url_for('charging.index'))

    # Pre-select vehicle if provided
    selected_vehicle_id = request.args.get('vehicle_id', type=int)

    return render_template('charging/form.html',
                           session=None,
                           vehicles=ev_vehicles,
                           charger_types=CHARGER_TYPES,
                           selected_vehicle_id=selected_vehicle_id)


@bp.route('/<int:session_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(session_id):
    """Edit an existing charging session"""
    session = db.get_or_404(ChargingSession, session_id)
    vehicles = current_user.get_all_vehicles()
    ev_vehicles = [v for v in vehicles if v.is_electric()]

    if session.vehicle not in vehicles:
        flash(_('Access denied'), 'error')
        return redirect(url_for('charging.index'))

    if request.method == 'POST':
        start_soc, err = parse_soc(request.form.get('start_soc'))
        if err is None:
            end_soc, err = parse_soc(request.form.get('end_soc'))
        if err:
            flash(err, 'error')
            return redirect(url_for('charging.edit', session_id=session.id))

        date_str = request.form.get('date')
        session.date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else session.date

        if request.form.get('start_time'):
            session.start_time = datetime.strptime(request.form.get('start_time'), '%H:%M').time()
        else:
            session.start_time = None
        if request.form.get('end_time'):
            session.end_time = datetime.strptime(request.form.get('end_time'), '%H:%M').time()
        else:
            session.end_time = None

        session.odometer = parse_decimal(request.form.get('odometer')) if request.form.get('odometer') else None
        session.kwh_added = parse_decimal(request.form.get('kwh_added')) if request.form.get('kwh_added') else None
        session.start_soc = start_soc
        session.end_soc = end_soc
        session.cost_per_kwh = parse_decimal(request.form.get('cost_per_kwh')) if request.form.get('cost_per_kwh') else None
        session.total_cost = parse_decimal(request.form.get('total_cost')) if request.form.get('total_cost') else None
        session.charger_type = request.form.get('charger_type')
        session.location = request.form.get('location')
        session.network = request.form.get('network')
        session.notes = request.form.get('notes')

        # Calculate total cost if not provided
        if session.kwh_added and session.cost_per_kwh and not session.total_cost:
            session.total_cost = round(session.kwh_added * session.cost_per_kwh, 2)

        db.session.commit()
        flash(_('Charging session updated successfully'), 'success')
        return redirect(url_for('charging.index'))

    return render_template('charging/form.html',
                           session=session,
                           vehicles=ev_vehicles,
                           charger_types=CHARGER_TYPES,
                           selected_vehicle_id=session.vehicle_id)


@bp.route('/<int:session_id>/delete', methods=['POST'])
@login_required
def delete(session_id):
    """Delete a charging session"""
    session = db.get_or_404(ChargingSession, session_id)
    vehicles = current_user.get_all_vehicles()

    if session.vehicle not in vehicles:
        flash(_('Access denied'), 'error')
        return redirect(url_for('charging.index'))

    db.session.delete(session)
    db.session.commit()
    flash(_('Charging session deleted successfully'), 'success')
    return redirect(url_for('charging.index'))
