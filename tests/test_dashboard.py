import re
from pathlib import Path

import pytest
from datetime import date, timedelta

from app import db
from app.models import Attachment, ChargingSession, Expense, FuelLog, Note, Reminder, Vehicle


class TestDashboard:
    def test_dashboard_requires_auth(self, client):
        resp = client.get('/dashboard', follow_redirects=False)
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']

    def test_dashboard_returns_200(self, auth_client):
        resp = auth_client.get('/dashboard')
        assert resp.status_code == 200

    def test_dashboard_without_vehicles(self, auth_client):
        resp = auth_client.get('/dashboard')
        assert resp.status_code == 200

    def test_dashboard_with_vehicles(self, auth_client, sample_vehicle):
        resp = auth_client.get('/dashboard')
        assert resp.status_code == 200
        assert b'Test Car' in resp.data

    def test_dashboard_with_fuel_logs(self, auth_client, sample_fuel_log):
        resp = auth_client.get('/dashboard')
        assert resp.status_code == 200

    def test_dashboard_with_expenses(self, auth_client, sample_expense):
        resp = auth_client.get('/dashboard')
        assert resp.status_code == 200

    def test_dashboard_charts_label_currency(self, auth_client, sample_expense):
        """The category chart must say what its money axis is in (#289)."""
        resp = auth_client.get('/dashboard')
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert 'const currency = "GBP";' in body
        # The category chart's value axis is x, because indexAxis is 'y'. The
        # monthly bar chart gave way to the hero's sparkline.
        assert body.count('text: currency') == 1
        assert body.count("' ' + currency") == 1

    def test_dashboard_chart_currency_is_escaped(self, app, auth_client, test_user):
        """A custom currency is free text, so it must not break out of the JS."""
        import json

        test_user.currency = 'X"Y'
        db.session.commit()
        resp = auth_client.get('/dashboard')
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert 'const currency = %s;' % json.dumps('X"Y') in body
        assert 'const currency = "X"Y";' not in body


class TestTimeline:
    def test_timeline_requires_auth(self, client, sample_vehicle):
        resp = client.get(f'/timeline/{sample_vehicle.id}', follow_redirects=False)
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']

    def test_timeline_returns_200(self, auth_client, sample_vehicle):
        resp = auth_client.get(f'/timeline/{sample_vehicle.id}')
        assert resp.status_code == 200

    def test_timeline_with_fuel_logs(self, auth_client, sample_fuel_log, sample_vehicle):
        resp = auth_client.get(f'/timeline/{sample_vehicle.id}')
        assert resp.status_code == 200

    def test_timeline_with_expenses(self, auth_client, sample_expense, sample_vehicle):
        resp = auth_client.get(f'/timeline/{sample_vehicle.id}')
        assert resp.status_code == 200

    def test_timeline_404_for_nonexistent(self, auth_client):
        resp = auth_client.get('/timeline/99999')
        assert resp.status_code == 404

    def test_timeline_chart_months_unique(self, auth_client, sample_vehicle):
        """The Monthly Costs chart must show 12 distinct calendar months (#270).

        The old 30-day stepping drifted against month boundaries, duplicating
        a month and skipping another depending on the date the page loaded.
        """
        import json
        import re
        resp = auth_client.get(f'/timeline/{sample_vehicle.id}')
        assert resp.status_code == 200
        match = re.search(r'const chartData = (\{.*?\});', resp.get_data(as_text=True))
        assert match, 'chart data not found in timeline page'
        labels = json.loads(match.group(1))['labels']
        from datetime import datetime
        expected = []
        year, month = datetime.now().year, datetime.now().month
        for _ in range(12):
            expected.append(datetime(year, month, 1).strftime('%b %Y'))
            month -= 1
            if month == 0:
                year, month = year - 1, 12
        assert labels == list(reversed(expected))

    def test_timeline_other_user_vehicle_redirects(self, auth_client, admin_user):
        # Create a vehicle owned by admin
        other_vehicle = Vehicle(
            owner_id=admin_user.id,
            name='Admin Car',
            vehicle_type='car',
            fuel_type='petrol',
        )
        db.session.add(other_vehicle)
        db.session.commit()

        resp = auth_client.get(f'/timeline/{other_vehicle.id}', follow_redirects=True)
        assert resp.status_code == 200
        # Should redirect to dashboard since user doesn't have access

    def test_timeline_shows_fuel_log_notes(self, auth_client, sample_fuel_log, sample_vehicle):
        """Notes recorded against an entry are visible on the timeline (#284)."""
        sample_fuel_log.notes = 'Filled up before the long drive'
        db.session.commit()

        resp = auth_client.get(f'/timeline/{sample_vehicle.id}')
        assert resp.status_code == 200
        assert b'Filled up before the long drive' in resp.data

    def test_timeline_shows_expense_notes(self, auth_client, sample_expense, sample_vehicle):
        sample_expense.notes = 'Independent garage, kept the receipt'
        db.session.commit()

        resp = auth_client.get(f'/timeline/{sample_vehicle.id}')
        assert resp.status_code == 200
        assert b'Independent garage, kept the receipt' in resp.data

    def test_timeline_shows_charging_notes(self, auth_client, test_user, sample_vehicle):
        session = ChargingSession(
            vehicle_id=sample_vehicle.id,
            user_id=test_user.id,
            date=date(2024, 2, 1),
            kwh_added=30.0,
            total_cost=12.0,
            notes='Rapid charger was half price',
        )
        db.session.add(session)
        db.session.commit()

        resp = auth_client.get(f'/timeline/{sample_vehicle.id}')
        assert resp.status_code == 200
        assert b'Rapid charger was half price' in resp.data

    def test_timeline_escapes_notes(self, auth_client, sample_expense, sample_vehicle):
        """Notes are user input, so they must be escaped rather than rendered."""
        sample_expense.notes = '<script>alert(1)</script>'
        db.session.commit()

        resp = auth_client.get(f'/timeline/{sample_vehicle.id}')
        assert resp.status_code == 200
        assert b'<script>alert(1)</script>' not in resp.data
        assert b'&lt;script&gt;alert(1)&lt;/script&gt;' in resp.data

    def test_timeline_shows_expense_attachment_link(self, auth_client, sample_expense, sample_vehicle):
        attachment = Attachment(
            filename='abc123_receipt.pdf',
            original_filename='receipt.pdf',
            expense_id=sample_expense.id,
            vehicle_id=sample_vehicle.id,
        )
        db.session.add(attachment)
        db.session.commit()

        resp = auth_client.get(f'/timeline/{sample_vehicle.id}')
        assert resp.status_code == 200
        assert b'receipt.pdf' in resp.data
        assert b'/api/uploads/abc123_receipt.pdf' in resp.data

    def test_timeline_shows_fuel_log_attachment_link(self, auth_client, sample_fuel_log, sample_vehicle):
        attachment = Attachment(
            filename='def456_fuel.jpg',
            original_filename='fuel-receipt.jpg',
            fuel_log_id=sample_fuel_log.id,
            vehicle_id=sample_vehicle.id,
        )
        db.session.add(attachment)
        db.session.commit()

        resp = auth_client.get(f'/timeline/{sample_vehicle.id}')
        assert resp.status_code == 200
        assert b'fuel-receipt.jpg' in resp.data
        assert b'/api/uploads/def456_fuel.jpg' in resp.data

    def test_timeline_attachments_not_shared_between_vehicles(self, auth_client, test_user,
                                                              sample_expense, sample_vehicle):
        """An attachment on another vehicle's expense must not leak onto this timeline."""
        other_vehicle = Vehicle(
            owner_id=test_user.id,
            name='Second Car',
            vehicle_type='car',
            fuel_type='petrol',
        )
        db.session.add(other_vehicle)
        db.session.commit()

        attachment = Attachment(
            filename='xyz789_other.pdf',
            original_filename='other-receipt.pdf',
            expense_id=sample_expense.id,
            vehicle_id=sample_vehicle.id,
        )
        db.session.add(attachment)
        db.session.commit()

        resp = auth_client.get(f'/timeline/{other_vehicle.id}')
        assert resp.status_code == 200
        assert b'other-receipt.pdf' not in resp.data


class TestDashboardReminderNoteCard:
    def test_category_card_shows_empty_state_without_data(self, auth_client):
        resp = auth_client.get('/dashboard')
        assert b'Expenses by Category' in resp.data
        assert b'id="categoryChart"' not in resp.data

    def test_card_lists_open_reminders_and_notes(self, auth_client, test_user, sample_vehicle):
        db.session.add(Reminder(
            vehicle_id=sample_vehicle.id, user_id=test_user.id,
            title='Renew insurance', reminder_type='insurance',
            due_date=date.today() - timedelta(days=3)))
        db.session.add(Reminder(
            vehicle_id=sample_vehicle.id, user_id=test_user.id,
            title='Already done', reminder_type='custom',
            due_date=date.today(), is_completed=True))
        db.session.add(Note(
            vehicle_id=sample_vehicle.id, user_id=test_user.id,
            title='DPF regen', content='Ran a regeneration'))
        db.session.commit()

        resp = auth_client.get('/dashboard')
        assert resp.status_code == 200
        assert b'id="rn-card"' in resp.data
        assert b'Renew insurance' in resp.data
        assert b'Already done' not in resp.data
        assert b'DPF regen' in resp.data


def _spend(vehicle, user, day, fuel=0, charging=0, other=0):
    if fuel:
        db.session.add(FuelLog(vehicle_id=vehicle.id, user_id=user.id, date=day, odometer=1000.0,
                               volume=10.0, price_per_unit=fuel / 10, total_cost=fuel, is_full_tank=True))
    if charging:
        db.session.add(ChargingSession(vehicle_id=vehicle.id, user_id=user.id, date=day,
                                       kwh_added=20.0, total_cost=charging))
    if other:
        db.session.add(Expense(vehicle_id=vehicle.id, user_id=user.id, date=day,
                               category='maintenance', description='Wipers', cost=other))
    db.session.commit()


def _month_start(offset=0):
    today = date.today()
    index = today.year * 12 + today.month - 1 + offset
    return date(index // 12, index % 12 + 1, 1)


def _hero(html):
    start = html.index('dashboard-hero')
    return html[start:html.index('</section>', start)]


class TestDashboardHero:
    def test_this_month_against_last_month(self, auth_client, test_user, sample_vehicle):
        # The first of the month counts: the date column is a plain date.
        _spend(sample_vehicle, test_user, _month_start(), fuel=60, charging=20, other=20)
        _spend(sample_vehicle, test_user, _month_start(-1), fuel=200)
        hero = _hero(auth_client.get('/dashboard').get_data(as_text=True))
        assert 'Spent in ' in hero
        assert '100.00<span class="ds-stat__unit">GBP</span>' in hero
        assert 'ds-badge--success">↓ 50%' in hero
        assert 'Last month: 200.00 GBP' in hero
        assert 'aria-label="Spending by type: Fuel 60%, Charging 20%, Other Expenses 20%"' in hero

    def test_spending_more_is_flagged(self, auth_client, test_user, sample_vehicle):
        _spend(sample_vehicle, test_user, _month_start(), other=150)
        _spend(sample_vehicle, test_user, _month_start(-1), other=100)
        assert 'ds-badge--danger">↑ 50%' in _hero(auth_client.get('/dashboard').get_data(as_text=True))

    def test_no_change_badge_without_last_month(self, auth_client, test_user, sample_vehicle):
        _spend(sample_vehicle, test_user, _month_start(), fuel=40)
        assert 'ds-badge' not in _hero(auth_client.get('/dashboard').get_data(as_text=True))

    def test_year_view(self, auth_client, test_user, sample_vehicle):
        this_year = date(date.today().year, 1, 1)
        _spend(sample_vehicle, test_user, this_year, fuel=300)
        _spend(sample_vehicle, test_user, date(this_year.year - 1, 6, 1), fuel=100)
        html = auth_client.get('/dashboard?period=year').get_data(as_text=True)
        hero = _hero(html)
        assert f'Spent in {this_year.year}' in hero
        assert 'ds-badge--danger">↑ 200%' in hero
        assert 'Last year: 100.00 GBP' in hero
        assert 'href="/dashboard?period=year" aria-current="page"' in html
        assert 'Average per month' in html

    def test_sparkline_and_projection(self, auth_client, test_user, sample_vehicle):
        _spend(sample_vehicle, test_user, _month_start(), fuel=50)
        html = auth_client.get('/dashboard').get_data(as_text=True)
        assert '<svg class="ds-sparkline"' in html
        assert 'On track for ' in html

    def test_empty_account(self, auth_client):
        html = auth_client.get('/dashboard').get_data(as_text=True)
        assert '0.00<span class="ds-stat__unit">GBP</span>' in _hero(html)
        assert 'ds-split' not in _hero(html)


class TestDashboardLists:
    def test_recent_activity_mixes_every_kind_newest_first(self, auth_client, test_user, sample_vehicle):
        _spend(sample_vehicle, test_user, date.today() - timedelta(days=3), fuel=30)
        _spend(sample_vehicle, test_user, date.today() - timedelta(days=2), charging=9)
        _spend(sample_vehicle, test_user, date.today() - timedelta(days=1), other=12)
        html = auth_client.get('/dashboard').get_data(as_text=True)
        table = html[html.index('ds-table--stack'):html.index('</table>')]
        kinds = re.findall(r'ds-badge--(\w+) ds-badge--square">([^<]+)<', table)
        assert [label for _, label in kinds] == ['Maintenance', 'Charging', 'Fuel']

    def test_vehicle_status_follows_its_reminders(self, auth_client, test_user, sample_vehicle):
        html = auth_client.get('/dashboard').get_data(as_text=True)
        assert 'ds-badge--success">All good' in html
        db.session.add(Reminder(vehicle_id=sample_vehicle.id, user_id=test_user.id, title='MOT',
                                reminder_type='custom', due_date=date.today() + timedelta(days=3)))
        db.session.commit()
        assert 'ds-badge--warning">Due soon' in auth_client.get('/dashboard').get_data(as_text=True)

    def test_overdue_reminder_needs_attention(self, auth_client, test_user, sample_vehicle):
        db.session.add(Reminder(vehicle_id=sample_vehicle.id, user_id=test_user.id, title='Insurance',
                                reminder_type='insurance', due_date=date.today() - timedelta(days=2)))
        db.session.commit()
        html = auth_client.get('/dashboard').get_data(as_text=True)
        assert '<li class="ds-attention ds-attention--danger">' in html
        assert 'Test Car · 2 days overdue' in html
        assert 'ds-badge--danger">Overdue' in html

    def test_reminders_hidden_from_the_menu_hide_the_card(self, auth_client, test_user):
        test_user.show_menu_reminders = False
        db.session.commit()
        assert 'Needs attention' not in auth_client.get('/dashboard').get_data(as_text=True)


LOCALES = sorted(p.name for p in (Path(__file__).resolve().parent.parent / 'app' / 'translations').iterdir()
                 if p.is_dir())


@pytest.mark.parametrize('locale', LOCALES)
def test_dashboard_renders_in_every_language(auth_client, test_user, sample_vehicle, locale):
    """The date line and month name come from Babel's locale data, and the
    hero's sentences are translated with a placeholder; every catalogue has
    to render them without error, in month and year view."""
    test_user.language = locale
    db.session.commit()
    _spend(sample_vehicle, test_user, _month_start(), fuel=10)
    for path in ('/dashboard', '/dashboard?period=year'):
        resp = auth_client.get(path)
        assert resp.status_code == 200, (locale, path)
        assert 'dashboard-hero' in resp.get_data(as_text=True)
