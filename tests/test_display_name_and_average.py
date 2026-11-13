"""A display name for the greeting, and average monthly running costs."""

from datetime import date

from app import db
from app.models import Expense
from app.routes.main import _add_months
from app.utils import utcnow


def _months_ago(n):
    now = utcnow()
    first = _add_months(now.replace(day=1, hour=0, minute=0, second=0, microsecond=0), -n)
    return date(first.year, first.month, 10)


class TestDisplayName:
    def test_greeting_falls_back_to_username(self, auth_client, test_user):
        html = auth_client.get('/dashboard').get_data(as_text=True)
        assert test_user.username in html

    def test_saved_name_is_used_in_greeting_and_sidebar(self, auth_client, test_user):
        resp = auth_client.post('/auth/settings', data={'display_name': '  Moshiur  ', 'email': test_user.email})
        assert resp.status_code == 302
        assert test_user.display_name == 'Moshiur'
        html = auth_client.get('/dashboard').get_data(as_text=True)
        assert ', Moshiur' in html
        assert '<span class="ds-side__username">Moshiur</span>' in html

    def test_blank_name_clears_back_to_username(self, auth_client, test_user):
        test_user.display_name = 'Someone'
        db.session.commit()
        auth_client.post('/auth/settings', data={'display_name': '   ', 'email': test_user.email})
        assert test_user.display_name is None
        assert test_user.shown_name == test_user.username

    def test_form_without_the_field_keeps_the_name(self, auth_client, test_user):
        test_user.display_name = 'Kept'
        db.session.commit()
        auth_client.post('/auth/settings', data={'email': test_user.email})
        assert test_user.display_name == 'Kept'

    def test_settings_shows_the_field(self, auth_client):
        html = auth_client.get('/auth/settings').get_data(as_text=True)
        assert 'name="display_name"' in html


class TestVehicleMonthAverage:
    def _add(self, vehicle, user, months_ago, cost):
        db.session.add(Expense(vehicle_id=vehicle.id, user_id=user.id, date=_months_ago(months_ago),
                               category='maintenance', description='x', cost=cost))

    def test_average_skips_current_month_and_empty_leading_months(self, auth_client, sample_vehicle, test_user):
        self._add(sample_vehicle, test_user, 0, 999)   # current month: not over, left out
        self._add(sample_vehicle, test_user, 3, 120)
        self._add(sample_vehicle, test_user, 1, 60)
        db.session.commit()
        html = auth_client.get(f'/vehicles/{sample_vehicle.id}').get_data(as_text=True)
        # Three months (3, 2, 1 ago), 180 in total.
        assert 'Average per month' in html
        assert '>60.00<' in html or '>60<' in html

    def test_no_history_shows_no_average(self, auth_client, sample_vehicle):
        html = auth_client.get(f'/vehicles/{sample_vehicle.id}').get_data(as_text=True)
        assert 'Average per month' not in html


class TestDashboardMonthAverage:
    def test_month_view_carries_the_year_average(self, auth_client, sample_vehicle, test_user):
        db.session.add(Expense(vehicle_id=sample_vehicle.id, user_id=test_user.id, date=date.today(),
                               category='maintenance', description='x', cost=120))
        db.session.commit()
        html = auth_client.get('/dashboard').get_data(as_text=True)
        assert ' a month' in html
