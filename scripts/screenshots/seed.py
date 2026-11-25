"""Add a richer sample garage to the demo database before retaking screenshots.

The demo seed creates two vehicles. The README and the landing page show four,
with charging sessions and a cheapest-fuel card, so this adds an EV, a scooter,
some charging sessions, fuel logs and station prices. Run it with the same
DEMO_MODE, SECRET_KEY and DATABASE_URL as the server (see take.cjs). It only
ever writes to the database those variables point at.
"""
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app import create_app, db  # noqa: E402
from app.models import ChargingSession, FuelLog, FuelPriceHistory, FuelStation, User, Vehicle

app = create_app()
with app.app_context():
    user = User.query.first()
    today = date.today()
    rng = random.Random(7)

    stations = [FuelStation(user_id=user.id, name=name, brand=brand, is_favorite=fav)
                for name, brand, fav in (('Riverside Fuel', 'Shell', True),
                                         ('Central Garage', None, False),
                                         ('Harbour Road Station', 'BP', False))]
    db.session.add_all(stations)
    db.session.flush()
    for station, price in zip(stations, (1.529, 1.489, 1.559)):
        db.session.add(FuelPriceHistory(station_id=station.id, user_id=user.id, date=today - timedelta(days=2),
                                        fuel_type='petrol', price_per_unit=price))

    ev = Vehicle(owner=user, name='Weekend EV', vehicle_type='car', make='Tesla', model='Model 3', year=2022,
                 registration='EV 22', fuel_type='electric', purchase_date=today - timedelta(days=500))
    scooter = Vehicle(owner=user, name='City Scooter', vehicle_type='motorbike', make='Honda', model='Dio',
                      year=2019, registration='CITY 19', fuel_type='petrol', tank_capacity=5,
                      purchase_date=today - timedelta(days=900))
    db.session.add_all([ev, scooter])
    db.session.flush()

    for i in range(9):
        kwh = round(rng.uniform(32, 48), 1)
        cost_kwh = round(rng.uniform(0.14, 0.22), 3)
        db.session.add(ChargingSession(
            vehicle_id=ev.id, user_id=user.id, date=today - timedelta(days=12 + i * 31),
            odometer=29_000 - i * 650, kwh_added=kwh, start_soc=rng.randint(18, 32),
            end_soc=rng.randint(78, 92), cost_per_kwh=cost_kwh, total_cost=round(kwh * cost_kwh, 2),
            charger_type='home', location='Home'))
    for i in range(8):
        volume = round(rng.uniform(3.6, 4.8), 1)
        price = round(1.50 + rng.random() * 0.1, 3)
        db.session.add(FuelLog(vehicle_id=scooter.id, user_id=user.id, date=today - timedelta(days=9 + i * 24),
                               odometer=14_000 - i * 210, volume=volume, price_per_unit=price,
                               total_cost=round(volume * price, 2), is_full_tank=True))
    db.session.commit()
    print('added 2 vehicles, 3 stations, 9 charging sessions and 8 scooter fills')
