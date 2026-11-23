"""A month's total sits in the same column as each entry's cost, so it carries
a "Total" label and a tinted band; without them it reads as one more entry."""
import pytest


@pytest.mark.parametrize('path', ['/fuel/', '/expenses/', '/timeline/{vehicle}'])
def test_month_row_labels_its_total(auth_client, sample_vehicle, sample_fuel_log,
                                    sample_expense, path):
    response = auth_client.get(path.format(vehicle=sample_vehicle.id))
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'class="ds-log__month"' in html
    assert 'ds-log__total-label' in html


def test_month_band_is_tinted_in_the_stylesheet():
    from pathlib import Path
    css = Path('app/static/css/src/app.css').read_text()
    assert '.ds-log__month { background: var(--ds-surface-sunken); }' in css
    assert '.ds-log__total-label' in css


def test_vehicle_spending_chart_fills_its_card(auth_client, test_user, sample_vehicle, _db):
    """The chart stretches to the card it shares a row with; the dashboard's
    copy keeps its fixed height."""
    from datetime import date
    from app.models import FuelLog
    # The chart only shows spending from the last few months.
    _db.session.add(FuelLog(vehicle_id=sample_vehicle.id, user_id=test_user.id,
                            date=date.today(), odometer=1000.0, volume=10.0,
                            price_per_unit=1.5, total_cost=15.0, is_full_tank=True))
    _db.session.commit()
    html = auth_client.get(f'/vehicles/{sample_vehicle.id}').get_data(as_text=True)
    assert 'ds-bars ds-bars--fill' in html
    assert 'vp-spend' in html
    dashboard = auth_client.get('/dashboard').get_data(as_text=True)
    assert 'ds-bars--fill' not in dashboard
