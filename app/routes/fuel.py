import os
import uuid
from datetime import date, datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy import extract, func
from sqlalchemy.orm import joinedload
from app import db
from app.utils import parse_decimal
from app.models import (
    Vehicle, FuelLog, Attachment, FuelStation, FuelPriceHistory, FUEL_TYPES,
    resolve_price_fuel_type,
)
from app.security import (
    validate_file_upload, secure_filename_with_uuid, validate_positive_number,
    get_safe_redirect_url
)
from flask_babel import gettext as _
from app.services.tessie import TessieService
from app.routes.log_helpers import (
    month_start as _month_start, group_by_month as _group_by_month,
    monthly_totals as _monthly_totals,
)

bp = Blueprint('fuel', __name__, url_prefix='/fuel')

# Generous cap so high-denomination currencies (IDR, KRW, ...) work (#393, #396).
MAX_UNIT_PRICE = 1_000_000
MAX_AMOUNT = 1_000_000_000  # total cost / sales tax
FUEL_LOGS_PER_PAGE = 50

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf'}


def allowed_file(filename):
    """Legacy function - use validate_file_upload for new code"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _stations():
    """Saved stations for the form's dropdown, favourites and most used first."""
    return FuelStation.query.order_by(
        FuelStation.is_favorite.desc(),
        FuelStation.times_used.desc()
    ).all()


def _form_rejected(vehicles, field, message, log=None):
    """Show the fuel form again with what was typed and why it was refused.

    Redirecting to a blank form made the user retype every field to fix one.
    The message sits under the field that failed. 422 rather than 200 so
    nothing reads the response as a saved log.
    """
    return render_template('fuel/form.html',
                           log=log,
                           vehicles=vehicles,
                           stations=_stations(),
                           fuel_types=FUEL_TYPES,
                           selected_vehicle_id=request.form.get('vehicle_id', type=int),
                           form=request.form,
                           error_field=field,
                           error_message=message), 422


# Consumption units where a smaller figure is the better one; the rest
# (mpg, km/L) read the other way round.
LOWER_IS_BETTER = {'L/100km', 'L / h'}
# How far a fill has to sit from the vehicle's average before the list
# marks it as better or worse, so ordinary noise stays unmarked.
CONSUMPTION_TREND_MARGIN = 0.05


def _consumption_trend(value, average, unit):
    """'better', 'worse' or None for one fill against its vehicle's average."""
    if not value or not average:
        return None
    ratio = value / average - 1
    if abs(ratio) < CONSUMPTION_TREND_MARGIN:
        return None
    lower = unit in LOWER_IS_BETTER
    return 'better' if (ratio < 0) == lower else 'worse'


def _fuel_rows(logs):
    """Each log with its consumption figure and how it compares to the average.

    The average is per vehicle and fuel type, worked out once for each pair
    on the page rather than once per row.
    """
    consumption_unit = current_user.consumption_unit
    volume_unit = current_user.volume_unit
    averages = {}
    rows = []
    for log in logs:
        unit = log.vehicle.get_consumption_unit() or consumption_unit
        value = log.get_consumption(consumption_unit, volume_unit)
        trend = average = None
        if value:
            key = (log.vehicle_id, log.effective_fuel_type)
            if key not in averages:
                averages[key] = log.vehicle.get_average_consumption(
                    consumption_unit, volume_unit, fuel_type=log.effective_fuel_type)
            average = averages[key]
            trend = _consumption_trend(value, average, unit)
        rows.append({'log': log, 'consumption': value, 'unit': unit,
                     'trend': trend, 'above_average': bool(trend) and value > average})
    return rows








@bp.route('/')
@login_required
def index():
    from app.models import ChargingSession
    from app.utils import utcnow

    vehicles = current_user.get_all_vehicles()
    # ?vehicle= narrows the page to one vehicle; anything else shows them all.
    selected_vehicle = next((v for v in vehicles if v.id == request.args.get('vehicle', type=int)), None)
    scope = [selected_vehicle] if selected_vehicle else vehicles
    vehicle_ids = [v.id for v in scope]
    has_charging = any(v.uses_charging() for v in scope)

    # Fuel and charging history are separate tabs.
    active_tab = 'charging' if request.args.get('tab') == 'charging' else 'fuel'
    page = request.args.get('page', 1, type=int)

    now = utcnow()
    this_month = _month_start(now)
    this_year = date(now.year, 1, 1)

    fuel_count = FuelLog.query.filter(FuelLog.vehicle_id.in_(vehicle_ids)).count()
    charging_count = ChargingSession.query.filter(ChargingSession.vehicle_id.in_(vehicle_ids)).count()

    context = dict(
        vehicles=vehicles,
        selected_vehicle=selected_vehicle,
        active_tab=active_tab,
        has_charging=has_charging or charging_count > 0,
        fuel_count=fuel_count,
        charging_count=charging_count,
    )

    if active_tab == 'charging':
        from app.routes.charging import charging_log
        return render_template('fuel/index.html',
                               logs=[], sales_tax_by_year=[],
                               **charging_log(vehicle_ids, page, FUEL_LOGS_PER_PAGE),
                               **context)

    # One page of fuel logs. Each row's consumption figure costs a few
    # queries, so rendering every log made the page grow without bound
    # (1,500+ queries and 1.4 MB of HTML at ~500 logs).
    pagination = FuelLog.query.options(joinedload(FuelLog.vehicle)).filter(
        FuelLog.vehicle_id.in_(vehicle_ids)
    ).order_by(FuelLog.date.desc(), FuelLog.odometer.desc(), FuelLog.id.desc()).paginate(
        page=page,
        per_page=FUEL_LOGS_PER_PAGE,
        error_out=False,
    )
    logs = pagination.items
    rows = _fuel_rows(logs)
    fuels_by_vehicle = {}
    for log in logs:
        fuels_by_vehicle.setdefault(log.vehicle_id, set()).add(log.effective_fuel_type)
    mixed_fuel_vehicles = {vid for vid, fuels in fuels_by_vehicle.items() if len(fuels) > 1}
    totals = _monthly_totals(FuelLog, FuelLog.total_cost, vehicle_ids,
                             [_month_start(log.date) for log in logs if log.date])

    # Sales tax paid per calendar year (#225): businesses reclaim it annually,
    # so the yearly total is what the page needs to show. Only years with tax
    # recorded appear, newest first, and the block is hidden entirely for users
    # who never log it.
    # Summed in the database over every log, not just the page shown.
    year = extract('year', FuelLog.date)
    sales_tax_by_year = [
        (int(row_year), round(total, 2))
        for row_year, total in db.session.query(year, func.sum(FuelLog.sales_tax))
        .filter(FuelLog.vehicle_id.in_(vehicle_ids),
                FuelLog.sales_tax.isnot(None), FuelLog.sales_tax != 0,
                FuelLog.date.isnot(None))
        .group_by(year).order_by(year.desc()).all()
        if total
    ]

    def fuel_sum(since):
        return db.session.query(func.sum(FuelLog.total_cost)).filter(
            FuelLog.vehicle_id.in_(vehicle_ids), FuelLog.date >= since).scalar() or 0

    # The latest fill's price, against the fill before it on the same vehicle
    # and fuel, so a jump at the pump is visible at a glance.
    last = FuelLog.query.filter(FuelLog.vehicle_id.in_(vehicle_ids)).order_by(
        FuelLog.date.desc(), FuelLog.odometer.desc(), FuelLog.id.desc()).first()
    price_change = None
    if last and last.price_per_unit:
        previous = FuelLog.query.filter(
            FuelLog.vehicle_id == last.vehicle_id,
            FuelLog.id != last.id,
            FuelLog.price_per_unit.isnot(None),
            FuelLog.date <= last.date,
            FuelLog.effective_fuel_type_filter(last.effective_fuel_type, last.vehicle.fuel_type),
        ).order_by(FuelLog.date.desc(), FuelLog.odometer.desc(), FuelLog.id.desc()).first()
        if previous:
            price_change = last.price_per_unit - previous.price_per_unit

    # An average only means something for one vehicle at a time.
    fuel_vehicles = [v for v in scope if v.fuel_logs.count()]
    average = None
    if len(fuel_vehicles) == 1:
        only = fuel_vehicles[0]
        average = {
            'value': only.get_average_consumption(current_user.consumption_unit, current_user.volume_unit),
            'unit': only.get_consumption_unit() or current_user.consumption_unit,
        }

    summary = {
        'month_cost': fuel_sum(this_month),
        'year_cost': fuel_sum(this_year),
        'last': last,
        'price_change': price_change,
        'average': average,
    }

    return render_template('fuel/index.html',
                           logs=logs,
                           groups=_group_by_month(rows, lambda row: row['log'].date, totals),
                           pagination=pagination,
                           sales_tax_by_year=sales_tax_by_year,
                           summary=summary,
                           mixed_fuel_vehicles=mixed_fuel_vehicles,
                           charging_sessions=[],
                           **context)


@bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    vehicles = current_user.get_all_vehicles()

    if not vehicles:
        flash(_('Please add a vehicle first'), 'info')
        return redirect(url_for('vehicles.new'))

    if request.method == 'POST':
        vehicle_id = int(request.form.get('vehicle_id'))
        vehicle = db.get_or_404(Vehicle, vehicle_id)

        # Check access
        if vehicle not in vehicles:
            flash(_('Access denied'), 'error')
            return redirect(url_for('fuel.index'))

        date_str = request.form.get('date')
        date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else datetime.now().date()

        # Validate numeric inputs. A failure re-renders the form with the
        # values as typed and the message under the field that failed.
        odometer, err = validate_positive_number(request.form.get('odometer'), 'Odometer', max_value=9999999)
        if err:
            return _form_rejected(vehicles, 'odometer', err)

        volume, err = validate_positive_number(request.form.get('volume'), 'Volume', max_value=10000)
        if err:
            return _form_rejected(vehicles, 'volume', err)

        price_per_unit, err = validate_positive_number(request.form.get('price_per_unit'), 'Price per unit', max_value=MAX_UNIT_PRICE)
        if err:
            return _form_rejected(vehicles, 'price_per_unit', err)

        discount_per_unit = None
        if request.form.get('discount_per_unit'):
            discount_per_unit, err = validate_positive_number(request.form.get('discount_per_unit'), 'Discount per unit', max_value=MAX_UNIT_PRICE)
            if err:
                return _form_rejected(vehicles, 'discount_per_unit', err)

        total_cost, err = validate_positive_number(request.form.get('total_cost'), 'Total cost', max_value=MAX_AMOUNT)
        if err:
            return _form_rejected(vehicles, 'total_cost', err)

        # Sales tax paid on the fill-up, already included in the total cost (#225)
        sales_tax = None
        if request.form.get('sales_tax'):
            sales_tax, err = validate_positive_number(request.form.get('sales_tax'), 'Sales tax', max_value=MAX_AMOUNT)
            if err:
                return _form_rejected(vehicles, 'sales_tax', err)

        # Distance run on this fuel — only bi-fuel vehicles need it (#221)
        fuel_distance = None
        if request.form.get('fuel_distance'):
            fuel_distance, err = validate_positive_number(
                request.form.get('fuel_distance'), 'Distance on this fuel', max_value=9999999)
            if err:
                return _form_rejected(vehicles, 'fuel_distance', err)

        # Derive the unit price from the amount paid when it was omitted.
        # Add the discount back because total_cost represents the amount paid
        # after the per-unit discount has been applied (#209).
        if price_per_unit is None and volume and total_cost is not None:
            price_per_unit = round(total_cost / volume + (discount_per_unit or 0), 3)
            price_per_unit, err = validate_positive_number(
                price_per_unit, 'Price per unit', max_value=MAX_UNIT_PRICE
            )
            if err:
                return _form_rejected(vehicles, 'total_cost', err)

        log = FuelLog(
            vehicle_id=vehicle_id,
            user_id=current_user.id,
            date=date,
            odometer=odometer or 0,
            odometer_confirmed=odometer is not None,
            volume=volume,
            price_per_unit=price_per_unit,
            discount_per_unit=discount_per_unit,
            total_cost=total_cost,
            sales_tax=sales_tax,
            fuel_type=request.form.get('fuel_type') or None,
            fuel_distance=fuel_distance,
            is_full_tank=request.form.get('is_full_tank') == 'on',
            is_missed=request.form.get('is_missed') == 'on',
            station=request.form.get('station'),
            notes=request.form.get('notes')
        )

        # Calculate total cost if not provided, applying any per-unit discount (#209)
        if log.volume and log.price_per_unit and not log.total_cost:
            effective_price = log.price_per_unit - (log.discount_per_unit or 0)
            log.total_cost = round(log.volume * effective_price, 2)

        db.session.add(log)
        db.session.commit()

        # Auto-save fuel price to history if station is selected
        station_id = request.form.get('station_id', type=int)
        if station_id and log.price_per_unit:
            station = db.session.get(FuelStation, station_id)
            if station:
                # Save price history
                price_history = FuelPriceHistory(
                    station_id=station_id,
                    user_id=current_user.id,
                    fuel_log_id=log.id,
                    date=log.date,
                    fuel_type=resolve_price_fuel_type(log.fuel_type, vehicle.fuel_type),
                    price_per_unit=log.price_per_unit
                )
                db.session.add(price_history)
                station.increment_usage()
                db.session.commit()

        # Handle attachment upload
        if 'attachment' in request.files:
            file = request.files['attachment']
            if file and file.filename and allowed_file(file.filename):
                filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
                file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))

                attachment = Attachment(
                    filename=filename,
                    original_filename=file.filename,
                    file_type=file.filename.rsplit('.', 1)[1].lower(),
                    fuel_log_id=log.id
                )
                db.session.add(attachment)
                db.session.commit()

        flash(_('Fuel log added successfully'), 'success')

        # Redirect back to vehicle page if we came from there (#283)
        if request.form.get('return_to') == 'vehicle':
            return redirect(url_for('vehicles.view', vehicle_id=vehicle_id))

        return redirect(url_for('fuel.index'))

    # Pre-select vehicle: explicit param > default vehicle preference
    selected_vehicle_id = request.args.get('vehicle_id', type=int) or current_user.default_vehicle_id

    # Get all fuel stations for dropdown (stations are system-wide)
    stations = _stations()

    return render_template('fuel/form.html',
                           log=None,
                           vehicles=vehicles,
                           stations=stations,
                           fuel_types=FUEL_TYPES,
                           selected_vehicle_id=selected_vehicle_id)


@bp.route('/<int:log_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(log_id):
    log = db.get_or_404(FuelLog, log_id)
    vehicles = current_user.get_all_vehicles()

    # Check access
    if log.vehicle not in vehicles:
        flash(_('Access denied'), 'error')
        return redirect(url_for('fuel.index'))

    if request.method == 'POST':
        # Validate a derived price before mutating the log or its station history.
        derived_price = None
        # An explicit blank still means clear the price (and its history).
        if 'price_per_unit' not in request.form:
            values = {}
            for field, label, maximum in (
                ('volume', 'Volume', 10000),
                ('total_cost', 'Total cost', MAX_AMOUNT),
                ('discount_per_unit', 'Discount per unit', MAX_UNIT_PRICE),
            ):
                values[field], err = validate_positive_number(
                    request.form.get(field), label, max_value=maximum)
                if err:
                    return _form_rejected(vehicles, field, err, log=log)
            if values['volume'] and values['total_cost'] is not None:
                derived_price, err = validate_positive_number(
                    round(values['total_cost'] / values['volume']
                          + (values['discount_per_unit'] or 0), 3),
                    'Price per unit', max_value=MAX_UNIT_PRICE)
                if err:
                    return _form_rejected(vehicles, 'total_cost', err, log=log)

        # Capture old values before updating for price history sync
        old_price = log.price_per_unit
        old_date = log.date

        new_vehicle_id = request.form.get('vehicle_id', type=int)
        if new_vehicle_id:
            new_vehicle = db.get_or_404(Vehicle, new_vehicle_id)
            if new_vehicle in vehicles:
                log.vehicle_id = new_vehicle_id
        date_str = request.form.get('date')
        log.date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else log.date
        reading, err = validate_positive_number(request.form.get('odometer'), 'Odometer', max_value=9999999)
        if err:
            db.session.rollback()
            return _form_rejected(vehicles, 'odometer', err, log=log)
        log.odometer = reading or 0
        log.odometer_confirmed = reading is not None
        log.volume = parse_decimal(request.form.get('volume')) if request.form.get('volume') else None
        log.price_per_unit = parse_decimal(request.form.get('price_per_unit')) if request.form.get('price_per_unit') else derived_price
        log.discount_per_unit = parse_decimal(request.form.get('discount_per_unit')) if request.form.get('discount_per_unit') else None
        log.total_cost = parse_decimal(request.form.get('total_cost')) if request.form.get('total_cost') else None
        log.sales_tax = parse_decimal(request.form.get('sales_tax')) if request.form.get('sales_tax') else None
        log.fuel_type = request.form.get('fuel_type') or None
        log.fuel_distance = parse_decimal(request.form.get('fuel_distance')) if request.form.get('fuel_distance') else None
        log.is_full_tank = request.form.get('is_full_tank') == 'on'
        log.is_missed = request.form.get('is_missed') == 'on'
        log.station = request.form.get('station')
        log.notes = request.form.get('notes')

        # Calculate total cost if not provided, applying any per-unit discount (#209)
        if log.volume and log.price_per_unit and not log.total_cost:
            effective_price = log.price_per_unit - (log.discount_per_unit or 0)
            log.total_cost = round(log.volume * effective_price, 2)

        # Reconcile fuel price history with the edited log.
        # Issue #170: linking a station to an existing log via edit must
        # both create the price-history row (so it shows in "cheapest fuel")
        # and bump the station's `times_used` counter.
        station_id = request.form.get('station_id', type=int)
        # Prefer the exact FK link (#254); fall back to the legacy heuristic
        # only for rows created before fuel_log_id existed. Restricting the
        # heuristic to unlinked rows stops it from grabbing a different log's
        # entry that happens to share the same date and price.
        existing_entry = FuelPriceHistory.query.filter_by(fuel_log_id=log.id).first()
        if not existing_entry and old_price and old_date:
            existing_entry = FuelPriceHistory.query.filter_by(
                user_id=current_user.id,
                date=old_date,
                price_per_unit=old_price,
                fuel_log_id=None,
            ).first()
            if existing_entry:
                # Adopt the legacy row so future edits match exactly.
                existing_entry.fuel_log_id = log.id

        if existing_entry:
            if not log.price_per_unit:
                db.session.delete(existing_entry)
            else:
                existing_entry.price_per_unit = log.price_per_unit
                existing_entry.date = log.date
                # Keep the charted fuel type in step with the log (#268):
                # changing a fill-up from petrol to diesel has to move the
                # price row onto the diesel series too.
                existing_entry.fuel_type = resolve_price_fuel_type(
                    log.fuel_type, log.vehicle.fuel_type
                )
                if station_id and existing_entry.station_id != station_id:
                    new_station = db.session.get(FuelStation, station_id)
                    if new_station:
                        # Reassigning the log moves the usage count too (#252):
                        # decrement the station we're leaving before bumping the
                        # new one, so no station is over-counted.
                        old_station = existing_entry.station
                        if old_station and old_station.times_used:
                            old_station.times_used = max(0, old_station.times_used - 1)
                        existing_entry.station_id = station_id
                        new_station.increment_usage()
        elif station_id and log.price_per_unit:
            new_station = db.session.get(FuelStation, station_id)
            if new_station:
                db.session.add(FuelPriceHistory(
                    station_id=station_id,
                    user_id=current_user.id,
                    fuel_log_id=log.id,
                    date=log.date,
                    fuel_type=resolve_price_fuel_type(log.fuel_type, log.vehicle.fuel_type),
                    price_per_unit=log.price_per_unit,
                ))
                new_station.increment_usage()

        # Handle attachment upload
        if 'attachment' in request.files:
            file = request.files['attachment']
            if file and file.filename and allowed_file(file.filename):
                filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
                file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))

                attachment = Attachment(
                    filename=filename,
                    original_filename=file.filename,
                    file_type=file.filename.rsplit('.', 1)[1].lower(),
                    fuel_log_id=log.id
                )
                db.session.add(attachment)

        db.session.commit()
        flash(_('Fuel log updated successfully'), 'success')

        # Redirect back to vehicle page if we came from there (#283)
        if request.form.get('return_to') == 'vehicle':
            return redirect(url_for('vehicles.view', vehicle_id=log.vehicle_id))

        return redirect(url_for('fuel.index'))

    # Get all fuel stations for dropdown (stations are system-wide)
    stations = _stations()

    return render_template('fuel/form.html',
                           log=log,
                           vehicles=vehicles,
                           stations=stations,
                           fuel_types=FUEL_TYPES,
                           selected_vehicle_id=log.vehicle_id)


@bp.route('/<int:log_id>/delete', methods=['POST'])
@login_required
def delete(log_id):
    log = db.get_or_404(FuelLog, log_id)
    vehicles = current_user.get_all_vehicles()

    # Check access
    if log.vehicle not in vehicles:
        flash(_('Access denied'), 'error')
        return redirect(url_for('fuel.index'))

    vehicle_id = log.vehicle_id

    # Delete attachments
    for attachment in log.attachments.all():
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], attachment.filename)
        if os.path.exists(file_path):
            os.remove(file_path)

    # Clean up matching fuel price history entries and keep each affected
    # station's usage counter in step with the chart view (#252): deleting a
    # log must decrement the overview "used N times" counter, not just drop the
    # price-history row the chart reads from.
    # Prefer the exact FK link (#254); the legacy heuristic only considers
    # unlinked rows so it can never delete another log's price entry.
    entries = FuelPriceHistory.query.filter_by(fuel_log_id=log.id).all()
    if not entries and log.price_per_unit and log.date:
        entries = FuelPriceHistory.query.filter(
            FuelPriceHistory.user_id == current_user.id,
            FuelPriceHistory.date == log.date,
            FuelPriceHistory.price_per_unit == log.price_per_unit,
            FuelPriceHistory.fuel_log_id.is_(None)
        ).all()
    if entries:
        for entry in entries:
            station = entry.station
            if station and station.times_used:
                station.times_used = max(0, station.times_used - 1)
            db.session.delete(entry)

    db.session.delete(log)
    db.session.commit()
    flash(_('Fuel log deleted successfully'), 'success')
    # Redirect back to vehicle page if we came from there (#283), using the
    # same `return_to` token the new and edit routes take (#312).
    return_to = request.form.get('return_to') or request.args.get('return_to')
    if return_to == 'vehicle':
        return redirect(url_for('vehicles.view', vehicle_id=vehicle_id))

    # Return to wherever the delete came from (#298): deleting from the fuel
    # log should stay there rather than bouncing to the vehicle page. `next`
    # stays supported so existing links and bookmarks keep working.
    next_url = get_safe_redirect_url(request.form.get('next'), default=None)
    return redirect(next_url or url_for('vehicles.view', vehicle_id=vehicle_id))


@bp.route('/<int:log_id>/attachments/<int:attachment_id>/delete', methods=['POST'])
@login_required
def delete_attachment(log_id, attachment_id):
    log = db.get_or_404(FuelLog, log_id)
    vehicles = current_user.get_all_vehicles()

    if log.vehicle not in vehicles:
        flash(_('Access denied'), 'error')
        return redirect(url_for('fuel.index'))

    attachment = db.get_or_404(Attachment, attachment_id)
    if attachment.fuel_log_id != log_id:
        flash(_('Access denied'), 'error')
        return redirect(url_for('fuel.edit', log_id=log_id))

    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], attachment.filename)
    if os.path.exists(file_path):
        os.remove(file_path)

    db.session.delete(attachment)
    db.session.commit()
    flash(_('Attachment deleted'), 'success')
    return redirect(url_for('fuel.edit', log_id=log_id))


def get_last_fuel_price(vehicle, user_id):
    """Get the most recent fuel price for a vehicle, or None."""
    last_log = FuelLog.query.filter(
        FuelLog.vehicle_id == vehicle.id,
        FuelLog.user_id == user_id,
        FuelLog.effective_fuel_type_filter(vehicle.get_primary_fuel_type(), vehicle.fuel_type),
        FuelLog.price_per_unit >= 0,
        FuelLog.price_per_unit <= MAX_UNIT_PRICE
    ).order_by(FuelLog.date.desc(), FuelLog.id.desc()).first()
    return last_log.price_per_unit if last_log else None


@bp.route('/quick', methods=['GET', 'POST'])
@login_required
def quick():
    """Quick entry mode - simplified single-screen fuel entry for mobile"""
    from app.models import FuelStation

    vehicles = current_user.get_all_vehicles()
    # The quick-fuel sheet loads the bare form (?fragment=1) and saves over
    # fetch, asking for JSON so it can stay on the page it was opened from.
    in_sheet = request.args.get('fragment') == '1'
    wants_json = request.accept_mimetypes.best == 'application/json'

    if not vehicles:
        if in_sheet:
            return render_template('fuel/_quick_no_vehicle.html')
        flash(_('Please add a vehicle first'), 'info')
        return redirect(url_for('vehicles.new'))

    # Get all fuel stations for dropdown (stations are system-wide)
    stations = _stations()

    if request.method == 'POST':
        vehicle_id = int(request.form.get('vehicle_id'))
        vehicle = db.get_or_404(Vehicle, vehicle_id)

        if vehicle not in vehicles:
            if wants_json:
                return jsonify(ok=False, message=_('Access denied')), 403
            flash(_('Access denied'), 'error')
            return redirect(url_for('fuel.quick'))

        volume = parse_decimal(request.form.get('volume')) if request.form.get('volume') else None
        total_cost = parse_decimal(request.form.get('total_cost')) if request.form.get('total_cost') else None
        price_per_unit = parse_decimal(request.form.get('price_per_unit')) if request.form.get('price_per_unit') else None

        # Derive missing value if two of the three are provided
        if volume and price_per_unit is not None and total_cost is None:
            total_cost = round(volume * price_per_unit, 2)
        elif volume and total_cost is not None and price_per_unit is None:
            price_per_unit = round(total_cost / volume, 3)

        log = FuelLog(
            vehicle_id=vehicle_id,
            user_id=current_user.id,
            date=datetime.now().date(),
            odometer=parse_decimal(request.form.get('odometer')),
            volume=volume,
            total_cost=total_cost,
            price_per_unit=price_per_unit,
            fuel_type=request.form.get('fuel_type') or None,
            is_full_tank=request.form.get('is_full_tank') == 'on',
            station=request.form.get('station'),
        )

        db.session.add(log)
        db.session.commit()

        # Associate with a saved station the same way fuel.new() does (#252):
        # record a FuelPriceHistory row and bump the usage counter together, so
        # quick logs show up in the station chart view and keep the overview
        # counter in step. Prefer the station_id sent by the dropdown; fall back
        # to a name match for manually typed stations.
        station_id = request.form.get('station_id', type=int)
        station = None
        if station_id:
            station = db.session.get(FuelStation, station_id)
        else:
            station_name = request.form.get('station')
            if station_name:
                station = FuelStation.query.filter_by(
                    user_id=current_user.id,
                    name=station_name
                ).first()
        if station and log.price_per_unit is not None:
            db.session.add(FuelPriceHistory(
                station_id=station.id,
                user_id=current_user.id,
                fuel_log_id=log.id,
                date=log.date,
                fuel_type=resolve_price_fuel_type(log.fuel_type, vehicle.fuel_type),
                price_per_unit=log.price_per_unit,
            ))
            station.increment_usage()
            db.session.commit()

        if wants_json:
            return jsonify(ok=True, message=_('Fuel log added!'),
                           add_another=bool(request.form.get('add_another')))

        flash(_('Fuel log added!'), 'success')

        # Return to quick entry or vehicle page based on preference
        if request.form.get('add_another'):
            return redirect(url_for('fuel.quick', vehicle_id=vehicle_id))
        return redirect(url_for('vehicles.view', vehicle_id=vehicle_id))

    # Pre-select vehicle: explicit param > default vehicle preference > single vehicle
    selected_vehicle_id = request.args.get('vehicle_id', type=int)
    if not selected_vehicle_id and current_user.default_vehicle_id in [v.id for v in vehicles]:
        selected_vehicle_id = current_user.default_vehicle_id
    if not selected_vehicle_id and len(vehicles) == 1:
        selected_vehicle_id = vehicles[0].id

    # Resolve defaults only from vehicles this user can access.
    vehicle = next((v for v in vehicles if v.id == selected_vehicle_id), vehicles[0])
    if selected_vehicle_id != vehicle.id:
        selected_vehicle_id = None
    last_odometer = vehicle.get_last_odometer()
    last_prices = {v.id: get_last_fuel_price(v, current_user.id) for v in vehicles}
    last_price = last_prices[vehicle.id]

    return render_template('fuel/_quick_form.html' if in_sheet else 'fuel/quick.html',
                           p='qf-' if in_sheet else '',
                           in_sheet=in_sheet,
                           vehicles=vehicles,
                           stations=stations,
                           selected_vehicle_id=selected_vehicle_id,
                           last_odometer=last_odometer,
                           last_price=last_price,
                           last_prices=last_prices)
