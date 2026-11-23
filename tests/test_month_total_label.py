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
