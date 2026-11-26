"""Home Assistant Integration API endpoints.

These endpoints provide REST API access for Home Assistant integration.
Configure in Home Assistant using the RESTful integration or custom sensors.

Example Home Assistant configuration (configuration.yaml):

```yaml
rest:
  - resource: http://your-ododash-server:5050/api/ha/vehicles
    headers:
      Authorization: Bearer YOUR_API_TOKEN
    sensor:
      - name: "OdoDash Vehicles Count"
        value_template: "{{ value_json.count }}"

sensor:
  - platform: rest
    name: "Car Fuel Economy"
    resource: http://your-ododash-server:5050/api/ha/vehicles/1/stats
    headers:
      Authorization: Bearer YOUR_API_TOKEN
    value_template: "{{ value_json.avg_consumption }}"
    unit_of_measurement: "L/100km"
    json_attributes:
      - total_distance
      - total_fuel
      - total_cost
```
"""

from flask import Blueprint, jsonify, request, current_app
from functools import wraps
from app import db
from app.models import (
    User, Vehicle, FuelLog, Expense, MaintenanceSchedule,
    RecurringExpense, Document, Reminder, ChargingSession
)
from datetime import date, timedelta
from sqlalchemy import func
from config import APP_VERSION

bp = Blueprint('homeassistant', __name__, url_prefix='/api/ha')


def _accessible_vehicles(user):
    """Vehicles the token's user can see: owned, shared with them, and
    instance-shared — the same set the web UI and /api/v1 use."""
    return user.get_all_vehicles()


def _find_vehicle(user, vehicle_id):
    """One accessible vehicle by id, or None."""
    for v in _accessible_vehicles(user):
        if v.id == vehicle_id:
            return v
    return None


def _consumption_unit(vehicle):
    """Consumption unit matching how this vehicle's readings are stored.

    Odometer values are stored in the vehicle's effective odometer unit, so
    the consumption unit has to follow that rather than the account's
    preference. An hours-metered vehicle has no distance-based figure.
    """
    if vehicle.tracks_hours():
        return None
    return 'mpg' if vehicle.get_effective_odometer_unit() == 'mi' else 'L/100km'


def token_required(f):
    """Decorator to require API token authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({'error': 'Authorization header required'}), 401

        try:
            scheme, token = auth_header.split(' ', 1)
            if scheme.lower() != 'bearer':
                return jsonify({'error': 'Bearer token required'}), 401
        except ValueError:
            return jsonify({'error': 'Invalid authorization header'}), 401

        # The scoped Home Assistant key, or the account API key so
        # existing YAML setups keep working.
        user = User.get_by_ha_token(token) or User.get_by_api_key(token)
        if not user:
            return jsonify({'error': 'Invalid API token'}), 401

        # Add user to kwargs for route access
        kwargs['user'] = user
        return f(*args, **kwargs)
    return decorated


@bp.route('/status')
@token_required
def status(user):
    """Health check endpoint for Home Assistant availability sensor."""
    return jsonify({
        'status': 'online',
        'user': user.username,
        'version': APP_VERSION
    })


@bp.route('/vehicles')
@token_required
def vehicles(user):
    """List all vehicles with basic stats."""
    vehicles = _accessible_vehicles(user)

    result = {
        'count': len(vehicles),
        'vehicles': []
    }

    for v in vehicles:
        vehicle_data = {
            'id': v.id,
            'name': v.name,
            'make': v.make,
            'model': v.model,
            'year': v.year,
            'registration': v.registration,
            'fuel_type': v.fuel_type,
            'current_odometer': v.get_last_odometer(),
            # current_odometer is the raw stored reading, so for an
            # hours-metered vehicle it is engine hours and the account's
            # distance preference does not describe it (#324).
            'unit_distance': v.get_reading_unit(),
            'unit_volume': user.volume_unit,
            'currency': user.currency
        }
        result['vehicles'].append(vehicle_data)

    return jsonify(result)


@bp.route('/vehicles/<int:vehicle_id>')
@token_required
def vehicle_detail(vehicle_id, user):
    """Get detailed vehicle information."""
    vehicle = _find_vehicle(user, vehicle_id)
    if not vehicle:
        return jsonify({'error': 'Vehicle not found'}), 404

    return jsonify({
        'id': vehicle.id,
        'name': vehicle.name,
        'make': vehicle.make,
        'model': vehicle.model,
        'year': vehicle.year,
        'registration': vehicle.registration,
        'fuel_type': vehicle.fuel_type,
        'current_odometer': vehicle.get_last_odometer(),
        'unit_distance': vehicle.get_reading_unit(),
        'unit_volume': user.volume_unit,
        'currency': user.currency
    })


def _vehicle_stats(vehicle, user, days=None):
    """Fuel, expense and consumption figures for one vehicle.

    ``days`` limits the fuel and expense totals to that many days back and
    measures distance from the odometer reading at the start of that window;
    ``None`` means all time. Shared by ``/vehicles/<id>/stats`` and
    ``/overview`` so the two never disagree.
    """
    since_date = date.today() - timedelta(days=days) if days else None
    if days:
        fuel_query = FuelLog.query.filter(
            FuelLog.vehicle_id == vehicle.id,
            FuelLog.date >= since_date
        )
        expense_query = Expense.query.filter(
            Expense.vehicle_id == vehicle.id,
            Expense.date >= since_date
        )
    else:
        fuel_query = FuelLog.query.filter_by(vehicle_id=vehicle.id)
        expense_query = Expense.query.filter_by(vehicle_id=vehicle.id)

    # Calculate fuel stats
    fuel_logs = fuel_query.order_by(FuelLog.odometer.asc()).all()

    total_fuel = sum(log.volume for log in fuel_logs)
    total_fuel_cost = sum(log.total_cost for log in fuel_logs)

    # Keep fuel consumption tied to the span between fuel logs.
    if len(fuel_logs) >= 2:
        fuel_distance = fuel_logs[-1].odometer - fuel_logs[0].odometer
    else:
        fuel_distance = 0

    if since_date:
        total_distance = vehicle.get_distance_between(
            since_date, date.today() + timedelta(days=1)
        )
    else:
        total_distance = vehicle.get_total_distance()

    # Calculate average consumption
    # Skip first fill for consumption calculation (don't know previous fill level)
    consumption_unit = _consumption_unit(vehicle)
    if consumption_unit is None:
        avg_consumption = None
    elif len(fuel_logs) >= 2 and fuel_distance > 0:
        consumption_fuel = sum(log.volume for log in fuel_logs[1:])
        if consumption_unit == 'mpg':
            # MPG (higher is better)
            avg_consumption = fuel_distance / consumption_fuel if consumption_fuel > 0 else 0
        else:
            # L/100km (lower is better)
            avg_consumption = (consumption_fuel / fuel_distance) * 100 if fuel_distance > 0 else 0
    else:
        avg_consumption = 0

    # Calculate expense totals
    total_expenses = expense_query.with_entities(func.sum(Expense.cost)).scalar() or 0

    # Get last fill date
    last_fill = FuelLog.query.filter_by(vehicle_id=vehicle.id).order_by(
        FuelLog.date.desc()
    ).first()

    return {
        'vehicle_id': vehicle.id,
        'vehicle_name': vehicle.name,
        'period_days': days if days else 'all',
        'total_distance': round(total_distance, 1),
        'total_fuel': round(total_fuel, 2),
        'total_fuel_cost': round(total_fuel_cost, 2),
        'total_expenses': round(float(total_expenses), 2),
        'total_cost': round(total_fuel_cost + float(total_expenses), 2),
        'avg_consumption': round(avg_consumption, 2) if avg_consumption is not None else None,
        'consumption_unit': consumption_unit,
        'fill_count': len(fuel_logs),
        'last_fill_date': last_fill.date.isoformat() if last_fill else None,
        'last_fill_volume': last_fill.volume if last_fill else None,
        'last_fill_cost': last_fill.total_cost if last_fill else None,
        'current_odometer': vehicle.get_last_odometer(),
        'distance_unit': vehicle.get_reading_unit(),
        'volume_unit': user.volume_unit,
        'currency': user.currency,
        'currency_symbol': vehicle.currency_symbol
    }


@bp.route('/vehicles/<int:vehicle_id>/stats')
@token_required
def vehicle_stats(vehicle_id, user):
    """Get vehicle statistics for Home Assistant sensors."""
    vehicle = _find_vehicle(user, vehicle_id)
    if not vehicle:
        return jsonify({'error': 'Vehicle not found'}), 404

    # Time period for stats (default: all time, or specify ?days=30)
    days = request.args.get('days', type=int)
    return jsonify(_vehicle_stats(vehicle, user, days))


def _collect_alerts(vehicles):
    """Active maintenance, recurring-expense, document and reminder alerts
    for the given vehicles. Shared by ``/alerts``, ``/summary`` and
    ``/overview``."""
    alerts = []
    vehicle_ids = [v.id for v in vehicles]

    # Check maintenance schedules
    schedules = MaintenanceSchedule.query.join(Vehicle).filter(
        Vehicle.id.in_(vehicle_ids),
        MaintenanceSchedule.is_active == True
    ).all()

    for schedule in schedules:
        current_odometer = schedule.vehicle.get_last_odometer()
        is_due = schedule.is_due(current_odometer)
        date_overdue = bool(schedule.next_due_date and schedule.next_due_date < date.today())
        odometer_overdue = bool(
            schedule.next_due_odometer is not None and
            current_odometer is not None and
            current_odometer > schedule.next_due_odometer
        )

        if is_due:
            alerts.append({
                'type': 'maintenance',
                'vehicle': schedule.vehicle.name,
                'vehicle_id': schedule.vehicle_id,
                'title': schedule.name,
                'status': 'overdue' if (date_overdue or odometer_overdue) else 'due',
                'due_odometer': schedule.next_due_odometer,
                'due_date': schedule.next_due_date.isoformat() if schedule.next_due_date else None
            })

    # Check recurring expenses
    recurring = RecurringExpense.query.join(Vehicle).filter(
        Vehicle.id.in_(vehicle_ids),
        RecurringExpense.is_active == True
    ).all()

    for item in recurring:
        if item.is_due():
            alerts.append({
                'type': 'recurring_expense',
                'vehicle': item.vehicle.name,
                'vehicle_id': item.vehicle_id,
                'title': item.name,
                'status': 'due',
                'due_date': item.next_due.isoformat() if item.next_due else None,
                'amount': item.amount
            })

    # Check expiring documents
    documents = Document.query.join(Vehicle).filter(
        Vehicle.id.in_(vehicle_ids)
    ).all()

    for doc in documents:
        if doc.is_expired():
            alerts.append({
                'type': 'document',
                'vehicle': doc.vehicle.name,
                'vehicle_id': doc.vehicle_id,
                'title': doc.title,
                'status': 'expired',
                'expiry_date': doc.expiry_date.isoformat() if doc.expiry_date else None
            })
        elif doc.is_expiring_soon():
            alerts.append({
                'type': 'document',
                'vehicle': doc.vehicle.name,
                'vehicle_id': doc.vehicle_id,
                'title': doc.title,
                'status': 'expiring_soon',
                'expiry_date': doc.expiry_date.isoformat() if doc.expiry_date else None
            })

    # Check reminders
    reminders = Reminder.query.join(Vehicle).filter(
        Vehicle.id.in_(vehicle_ids),
        Reminder.is_completed == False
    ).all()

    for reminder in reminders:
        if reminder.is_overdue():
            alerts.append({
                'type': 'reminder',
                'vehicle': reminder.vehicle.name,
                'vehicle_id': reminder.vehicle_id,
                'title': reminder.title,
                'status': 'overdue',
                'due_date': reminder.due_date.isoformat() if reminder.due_date else None
            })
        elif reminder.is_upcoming(reminder.notify_days_before or 7):
            alerts.append({
                'type': 'reminder',
                'vehicle': reminder.vehicle.name,
                'vehicle_id': reminder.vehicle_id,
                'title': reminder.title,
                'status': 'upcoming',
                'due_date': reminder.due_date.isoformat() if reminder.due_date else None
            })

    return alerts


@bp.route('/alerts')
@token_required
def alerts(user):
    """Get all active alerts for Home Assistant binary sensors."""
    alerts = _collect_alerts(_accessible_vehicles(user))
    return jsonify({
        'count': len(alerts),
        'has_alerts': len(alerts) > 0,
        'alerts': alerts
    })


@bp.route('/summary')
@token_required
def summary(user):
    """Get overall summary for Home Assistant dashboard."""
    vehicles = _accessible_vehicles(user)

    # Calculate totals
    total_vehicles = len(vehicles)
    total_distance = 0
    total_fuel_cost = 0
    total_expenses = 0
    alerts_count = 0

    for vehicle in vehicles:
        total_distance += vehicle.get_total_distance()
        fuel_logs = FuelLog.query.filter_by(vehicle_id=vehicle.id).all()
        total_fuel_cost += sum(log.total_cost for log in fuel_logs)

        # Get expense totals
        expenses = Expense.query.filter_by(vehicle_id=vehicle.id).with_entities(
            func.sum(Expense.cost)
        ).scalar() or 0
        total_expenses += float(expenses)

    # Count alerts
    alerts_count = len(_collect_alerts(vehicles))

    return jsonify({
        'total_vehicles': total_vehicles,
        'total_distance': round(total_distance, 1),
        'total_fuel_cost': round(total_fuel_cost, 2),
        'total_expenses': round(total_expenses, 2),
        'total_cost': round(total_fuel_cost + total_expenses, 2),
        'alerts_count': alerts_count,
        'has_alerts': alerts_count > 0
    })


def _last_charge(vehicle):
    """The latest charging session of an electric vehicle, or None."""
    if not vehicle.is_electric():
        return None
    session = ChargingSession.query.filter_by(vehicle_id=vehicle.id).order_by(
        ChargingSession.date.desc(), ChargingSession.id.desc()
    ).first()
    if not session:
        return None
    return {
        'date': session.date.isoformat() if session.date else None,
        'kwh_added': session.kwh_added,
        'start_soc': session.start_soc,
        'end_soc': session.end_soc,
        'total_cost': session.total_cost,
    }


@bp.route('/overview')
@token_required
def overview(user):
    """Everything the Home Assistant integration needs, in one request.

    One entry per accessible vehicle with its all-time stats, the cost of the
    last 30 days, the latest charge for an electric vehicle and that
    vehicle's alerts. Saves the integration 1 + N requests per poll.
    """
    vehicles = _accessible_vehicles(user)
    all_alerts = _collect_alerts(vehicles)

    result = []
    for v in vehicles:
        stats = _vehicle_stats(v, user)
        recent = _vehicle_stats(v, user, days=30)
        result.append({
            'id': v.id,
            'name': v.name,
            'make': v.make,
            'model': v.model,
            'year': v.year,
            'registration': v.registration,
            'fuel_type': v.fuel_type,
            'is_electric': v.is_electric(),
            'current_odometer': stats['current_odometer'],
            'distance_unit': stats['distance_unit'],
            'volume_unit': stats['volume_unit'],
            'currency_symbol': stats['currency_symbol'],
            'avg_consumption': stats['avg_consumption'],
            'consumption_unit': stats['consumption_unit'],
            'total_cost': stats['total_cost'],
            'total_fuel_cost': stats['total_fuel_cost'],
            'total_expenses': stats['total_expenses'],
            'cost_last_30_days': recent['total_cost'],
            'last_fill_date': stats['last_fill_date'],
            'last_fill_volume': stats['last_fill_volume'],
            'last_fill_cost': stats['last_fill_cost'],
            'last_charge': _last_charge(v),
            'alerts': [a for a in all_alerts if a['vehicle_id'] == v.id],
        })

    return jsonify({
        'version': APP_VERSION,
        'user': user.username,
        'currency': user.currency,
        'vehicles': result,
        'alerts_count': len(all_alerts),
    })


@bp.route('/fuel/add', methods=['POST'])
@token_required
def add_fuel(user):
    """Add a fuel log entry via API (for Home Assistant automations)."""
    data = request.get_json()

    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    required_fields = ['vehicle_id', 'date', 'odometer', 'volume', 'price_per_unit', 'total_cost']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400

    # Verify vehicle belongs to user
    try:
        vehicle = _find_vehicle(user, int(data['vehicle_id']))
    except (TypeError, ValueError):
        vehicle = None
    if not vehicle:
        return jsonify({'error': 'Vehicle not found'}), 404

    try:
        fuel_log = FuelLog(
            vehicle_id=vehicle.id,
            user_id=user.id,
            date=date.fromisoformat(data['date']),
            odometer=float(data['odometer']),
            volume=float(data['volume']),
            price_per_unit=float(data['price_per_unit']),
            total_cost=float(data['total_cost']),
            is_full_tank=data.get('is_full_tank', True),
            notes=data.get('notes', '')
        )

        db.session.add(fuel_log)
        db.session.commit()

        return jsonify({
            'success': True,
            'id': fuel_log.id,
            'message': 'Fuel log added successfully'
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400
