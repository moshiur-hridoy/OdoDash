"""Public demo mode.

With ``DEMO_MODE=1`` the app runs as a shared, throwaway showcase: a fresh
database is seeded with a year of realistic history under a ``demo``/``demo``
administrator, so every page has something to show. Visitors may add, edit
and delete vehicle data freely, but the handful of actions that would lock
the next visitor out (changing the password, managing users, restoring a
backup) or make the server talk to the outside world (SMTP, webhooks, DVLA,
Tessie, fuel-price feeds) are refused.

The demo is meant for hosts whose disk is wiped on restart, so a sleeping
free-tier instance comes back clean. Its strings are deliberately left out of
the translation catalogues: it is an English-language showcase.
"""
import fcntl
import os
import random
from datetime import date, time, timedelta

from flask import current_app, flash, jsonify, redirect, request, url_for
from flask_login import current_user

DEMO_USERNAME = 'demo'
DEMO_PASSWORD = 'demo'

DEMO_UPLOAD_LIMIT = 5 * 1024 * 1024

DISABLED_MESSAGE = 'This is disabled in the public demo.'

WRITE_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}

# Write endpoints refused in the demo. Pages stay viewable so visitors can see
# the admin screens; only submitting them is blocked.
BLOCKED_ENDPOINTS = {
    # Accounts — anything that could lock the shared login out.
    'auth.register',
    'auth.forgot_password',
    'auth.reset_password',
    'auth.toggle_admin',
    'auth.delete_user',
    'auth.edit_user',
    'auth.create_user',
    'auth.registration_settings',
    'api.generate_api_key',
    'api.revoke_api_key',
    'api.backup_restore_execute',
    # App-wide settings and outbound integrations.
    'auth.notifications',
    'auth.smtp_settings',
    'auth.branding',
    'auth.remove_logo',
    'auth.dvla_settings',
    'auth.uk_fuel_settings',
    'auth.tessie_settings',
    'api.test_notification',
    'api.test_smtp',
    'api.dvla_lookup',
    'api.dvla_test_key',
    'api.refresh_vehicle_dvla',
    'api.tessie_test_token',
    'api.refresh_vehicle_tessie',
    'api.import_tessie_charges',
    'stations.refresh_uk_prices',
    'stations.refresh_station_uk_prices',
}


def is_demo(app=None):
    return bool((app or current_app).config.get('DEMO_MODE'))


def _refuse():
    if request.path.startswith('/api/') or request.accept_mimetypes.best == 'application/json':
        return jsonify({'error': DISABLED_MESSAGE, 'code': 'demo_mode'}), 403
    flash(DISABLED_MESSAGE, 'warning')
    return redirect(request.referrer or url_for('main.dashboard'))


def _changes_credentials():
    """The preferences form also carries the email and password fields."""
    if request.form.get('new_password'):
        return True
    email = (request.form.get('email') or '').strip()
    return bool(email) and current_user.is_authenticated and email != current_user.email


def check_demo_request():
    """``before_request`` hook refusing the writes listed above."""
    if request.method not in WRITE_METHODS:
        return None
    if request.endpoint in BLOCKED_ENDPOINTS:
        return _refuse()
    if request.endpoint == 'auth.settings' and _changes_credentials():
        return _refuse()
    return None


def register_demo_hooks(app):
    app.config['MAX_CONTENT_LENGTH'] = DEMO_UPLOAD_LIMIT
    app.before_request(check_demo_request)

    @app.context_processor
    def inject_demo():
        return {
            'DEMO_MODE': True,
            'DEMO_USERNAME': DEMO_USERNAME,
            'DEMO_PASSWORD': DEMO_PASSWORD,
        }


def seed_demo_data(app):
    """Create the demo account and its sample history on an empty database.

    Gunicorn starts several workers that each build the app, so the check and
    the insert run under a file lock to stop two of them seeding at once.
    """
    from app import db
    from app.models import User

    lock_path = os.path.join(app.config['UPLOAD_FOLDER'], '.demo-seed.lock')
    with open(lock_path, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            if User.query.count() == 0:
                _seed(db)
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _seed(db):
    from app.models import (
        AppSettings, ChargingSession, Expense, FuelLog, MaintenanceSchedule,
        Reminder, Trip, User, Vehicle,
    )

    rng = random.Random(42)
    today = date.today()
    start = today - timedelta(days=365)

    user = User(username=DEMO_USERNAME, email='demo@example.com', is_admin=True,
                currency='USD', email_reminders=False, notification_method='none')
    user.set_password(DEMO_PASSWORD)
    db.session.add(user)
    AppSettings.set('registration_enabled', 'false')

    corolla = Vehicle(owner=user, name='Daily Driver', vehicle_type='car',
                      make='Toyota', model='Corolla', year=2019,
                      registration='DEMO 19', fuel_type='petrol', tank_capacity=50,
                      purchase_date=start - timedelta(days=900))
    tesla = Vehicle(owner=user, name='Weekend EV', vehicle_type='car',
                    make='Tesla', model='Model 3', year=2022,
                    registration='EV 22', fuel_type='electric', battery_capacity=60,
                    purchase_date=start - timedelta(days=200))
    db.session.add_all([corolla, tesla])

    # A fill-up every two to three weeks, with the price drifting over the year.
    odometer = 42_000.0
    day = start
    stations = ['Shell Main St', 'BP Riverside', 'Costco Fuel', 'Esso Highway']
    while day <= today:
        distance = rng.uniform(420, 620)
        odometer += distance
        litres = round(distance * rng.uniform(5.6, 6.8) / 100, 2)
        price = round(1.62 + 0.15 * rng.random() + 0.08 * ((day - start).days / 365), 3)
        db.session.add(FuelLog(vehicle=corolla, user=user, date=day, odometer=round(odometer),
                               volume=litres, price_per_unit=price,
                               total_cost=round(litres * price, 2), is_full_tank=True,
                               station=rng.choice(stations)))
        day += timedelta(days=rng.randint(14, 21))
    corolla_odometer = odometer

    # Mostly overnight charging at home, with the odd motorway fast charge.
    odometer = 18_000.0
    day = start
    while day <= today:
        fast = rng.random() < 0.2
        odometer += rng.uniform(180, 320)
        start_soc = rng.randint(15, 40)
        end_soc = rng.choice([80, 85, 90]) if fast else 90
        kwh = round(60 * (end_soc - start_soc) / 100 * 1.08, 1)
        rate = 0.42 if fast else 0.15
        db.session.add(ChargingSession(
            vehicle=tesla, user=user, date=day, odometer=round(odometer),
            start_time=time(14, 10) if fast else time(22, 30),
            end_time=time(14, 45) if fast else time(5, 30),
            kwh_added=kwh, start_soc=start_soc, end_soc=end_soc, cost_per_kwh=rate,
            total_cost=round(kwh * rate, 2),
            charger_type='dcfc' if fast else 'home',
            location='Ionity Services' if fast else 'Home',
            network='Ionity' if fast else None))
        day += timedelta(days=rng.randint(5, 9))

    def expense(vehicle, days_ago, category, description, cost, vendor=None, odometer=None):
        db.session.add(Expense(vehicle=vehicle, user=user, date=today - timedelta(days=days_ago),
                               category=category, description=description, cost=cost,
                               vendor=vendor, odometer=odometer))

    expense(corolla, 340, 'insurance', 'Annual insurance', 612.00, 'Admiral')
    expense(corolla, 300, 'tax', 'Road tax', 180.00)
    expense(corolla, 250, 'maintenance', 'Oil and filter change', 89.50, 'QuickLube', 46_200)
    expense(corolla, 190, 'repairs', 'Front brake pads', 214.00, 'City Garage', 49_100)
    expense(corolla, 120, 'inspection', 'Annual inspection', 54.85, 'City Garage')
    expense(corolla, 75, 'maintenance', 'Oil and filter change', 92.00, 'QuickLube', 54_600)
    expense(corolla, 40, 'accessories', 'All-weather floor mats', 49.99, 'Halfords')
    expense(tesla, 330, 'insurance', 'Annual insurance', 845.00, 'Tesla Insurance')
    expense(tesla, 210, 'maintenance', 'Tyre rotation', 45.00, 'Tesla Service')
    expense(tesla, 95, 'accessories', 'Home wallbox install', 690.00, 'Volt Electric')
    for days_ago in range(20, 360, 30):
        expense(corolla, days_ago, 'parking', 'City centre parking', round(rng.uniform(6, 18), 2))
        expense(tesla, days_ago + 9, 'cleaning', 'Car wash', 12.00, 'Splash Wash')
    for days_ago in range(35, 360, 60):
        expense(corolla, days_ago, 'tolls', 'Motorway toll', round(rng.uniform(4, 11), 2))

    # Business trips for the mileage log.
    clients = [('Office', 'Acme Corp HQ'), ('Office', 'Airport'), ('Home', 'Client site, Leeds'),
               ('Office', 'Trade fair'), ('Home', 'Supplier warehouse')]
    trip_odometer = corolla_odometer - 4_000
    for i in range(14):
        frm, to = clients[i % len(clients)]
        distance = round(rng.uniform(25, 160))
        db.session.add(Trip(vehicle=corolla, user=user, date=today - timedelta(days=12 + i * 23),
                            start_odometer=trip_odometer, end_odometer=trip_odometer + distance,
                            purpose='business' if i % 4 else 'personal',
                            description=f'Visit {to}', start_location=frm, end_location=to))
        trip_odometer += distance + 180

    db.session.add_all([
        Reminder(vehicle=corolla, user_rel=user, title='Insurance renewal', reminder_type='insurance',
                 due_date=today + timedelta(days=25), recurrence='yearly'),
        Reminder(vehicle=corolla, user_rel=user, title='Annual inspection', reminder_type='mot',
                 due_date=today + timedelta(days=245), recurrence='yearly'),
        Reminder(vehicle=tesla, user_rel=user, title='Tyre rotation', reminder_type='tire_change',
                 due_date=today + timedelta(days=12)),
        MaintenanceSchedule(vehicle=corolla, user=user, name='Oil change',
                            maintenance_type='oil_change', interval_km=8_000, interval_months=12,
                            last_performed_date=today - timedelta(days=75),
                            last_performed_odometer=54_600, next_due_odometer=62_600,
                            next_due_date=today + timedelta(days=290), estimated_cost=90),
    ])
    db.session.commit()
