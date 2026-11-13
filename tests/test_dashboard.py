import re
from pathlib import Path

import pytest
from datetime import date, timedelta

from app import db
from app.models import (Attachment, ChargingSession, Expense, FuelLog, FuelPriceHistory, FuelStation,
                        Note, Reminder, User, Vehicle)


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
        assert '200.00 GBP by this point last month' in hero
        assert 'aria-label="Spending by type: Fuel 60%, Charging 20%, Other Expenses 20%"' in hero

    def test_last_month_is_cut_off_at_the_same_day(self, auth_client, test_user, sample_vehicle):
        # Spending later in last month than today's date is not part of the
        # comparison: twelve days are set against twelve days.
        last_month = _month_start(-1)
        days_in_last_month = (_month_start() - last_month).days
        if date.today().day >= days_in_last_month:
            pytest.skip('today is past the end of last month, so nothing falls after the cut-off')
        _spend(sample_vehicle, test_user, _month_start(), fuel=50)
        _spend(sample_vehicle, test_user, last_month, fuel=100)
        _spend(sample_vehicle, test_user, last_month + timedelta(days=date.today().day), other=900)
        hero = _hero(auth_client.get('/dashboard').get_data(as_text=True))
        assert '100.00 GBP by this point last month' in hero
        assert 'ds-badge--success">↓ 50%' in hero

    def test_a_type_with_nothing_spent_is_left_out_of_the_split(self, auth_client, test_user, sample_vehicle):
        _spend(sample_vehicle, test_user, _month_start(), fuel=80, charging=20)
        hero = _hero(auth_client.get('/dashboard').get_data(as_text=True))
        assert 'aria-label="Spending by type: Fuel 80%, Charging 20%"' in hero
        assert 'Other Expenses' not in hero

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
        # 1 January last year is always before the cut-off; the last day of
        # last year never is, so it stays out of the comparison.
        _spend(sample_vehicle, test_user, date(this_year.year - 1, 1, 1), fuel=100)
        if date.today() < date(this_year.year, 12, 31):
            _spend(sample_vehicle, test_user, date(this_year.year - 1, 12, 31), other=500)
        html = auth_client.get('/dashboard?period=year').get_data(as_text=True)
        hero = _hero(html)
        assert f'Spent in {this_year.year}' in hero
        assert 'ds-badge--danger">↑ 200%' in hero
        assert '100.00 GBP by this point last year' in hero
        assert 'href="/dashboard?period=year" aria-current="page"' in html
        assert 'Average per month' in html

    def test_projection_without_a_sparkline(self, auth_client, test_user, sample_vehicle):
        _spend(sample_vehicle, test_user, _month_start(), fuel=50)
        html = auth_client.get('/dashboard').get_data(as_text=True)
        assert 'ds-sparkline' not in html
        assert 'On track for ' in html

    def test_driven_last_month_with_its_cost_per_km(self, auth_client, test_user, sample_vehicle):
        last = _month_start(-1)
        db.session.add_all([
            FuelLog(vehicle_id=sample_vehicle.id, user_id=test_user.id, date=_month_start(-2),
                    odometer=10000.0, volume=40.0, total_cost=0, is_full_tank=True),
            ChargingSession(vehicle_id=sample_vehicle.id, user_id=test_user.id, date=last + timedelta(days=9),
                            odometer=10500.0, kwh_added=20.0, total_cost=30.0),
            Expense(vehicle_id=sample_vehicle.id, user_id=test_user.id, date=last + timedelta(days=19),
                    category='maintenance', description='Tyres', cost=70.0, odometer=10800.0),
        ])
        db.session.commit()
        html = auth_client.get('/dashboard').get_data(as_text=True)
        month = {1: 'January', 2: 'February', 3: 'March', 4: 'April', 5: 'May', 6: 'June', 7: 'July',
                 8: 'August', 9: 'September', 10: 'October', 11: 'November', 12: 'December'}[last.month]
        assert f'Driven in {month}' in html
        # The vehicle logs km and the user reads miles: 800 km is 497 mi.
        assert '497<span class="ds-stat__unit">mi</span>' in html
        # 100 GBP over 497.1 mi last month; all time is the same spending over the same span.
        # One line: last month's rate in the accent, then the all-time one after a dot.
        assert ('<p class="ds-stat__note ds-stat__note--split"><span class="ds-stat__note--accent">'
                '0.20 GBP per mi</span> <span aria-hidden="true">·</span> <span>all time 0.20</span></p>') in html
        assert 'Cost per mi' not in html

    def test_month_bars_cover_the_last_six_months(self, auth_client, test_user, sample_vehicle):
        _spend(sample_vehicle, test_user, _month_start(), fuel=50)
        _spend(sample_vehicle, test_user, _month_start(-2), fuel=100)
        _spend(sample_vehicle, test_user, _month_start(-6), fuel=999)  # seven months back: left out
        hero = _hero(auth_client.get('/dashboard').get_data(as_text=True))
        columns = re.findall(r'class="ds-bars__col([^"]*)"[^>]*aria-label="([^"]+)"', hero)
        assert len(columns) == 6
        assert [c[1].split(': ')[1] for c in columns] == [
            '0.00 GBP', '0.00 GBP', '0.00 GBP', '100.00 GBP', '0.00 GBP', '50.00 GBP']
        assert columns[-1][0] == ' ds-bars__col--current'
        assert 'style="height: 100.0%"' in hero and 'style="height: 50.0%"' in hero
        assert 'aria-label="Monthly Spending"' in hero

    def test_year_bars_run_from_january(self, auth_client, test_user, sample_vehicle):
        _spend(sample_vehicle, test_user, _month_start(), fuel=50)
        hero = _hero(auth_client.get('/dashboard?period=year').get_data(as_text=True))
        months = date.today().month
        if months == 1:
            assert 'ds-bars' not in hero  # one column would only repeat the figure
        else:
            assert hero.count('ds-bars__col') - hero.count('ds-bars__col--current') == months

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

    def test_far_off_reminders_do_not_need_attention(self, auth_client, test_user, sample_vehicle):
        for title, days in (('Tyres', 12), ('Insurance', 30), ('Inspection', 31), ('Licence', 245)):
            db.session.add(Reminder(vehicle_id=sample_vehicle.id, user_id=test_user.id, title=title,
                                    reminder_type='custom', due_date=date.today() + timedelta(days=days)))
        db.session.commit()
        html = auth_client.get('/dashboard').get_data(as_text=True)
        card = html[html.index('id="rn-card"'):html.index('</section>', html.index('id="rn-card"'))]
        assert 'Tyres' in card and 'Insurance' in card
        assert 'Inspection' not in card and 'Licence' not in card
        assert '>2</span>' in card  # the count follows the list, not every open reminder

    def test_the_card_lists_four_and_counts_them_all(self, auth_client, test_user, sample_vehicle):
        for day in range(6):
            db.session.add(Reminder(vehicle_id=sample_vehicle.id, user_id=test_user.id, title=f'Task {day}',
                                    reminder_type='custom', due_date=date.today() + timedelta(days=day)))
        db.session.commit()
        html = auth_client.get('/dashboard').get_data(as_text=True)
        card = html[html.index('id="rn-card"'):html.index('</section>', html.index('id="rn-card"'))]
        assert card.count('<li class="ds-attention') == 4
        assert 'Task 3' in card and 'Task 4' not in card
        assert '>6</span>' in card

    def test_only_far_off_reminders_say_nothing_is_due_soon(self, auth_client, test_user, sample_vehicle):
        db.session.add(Reminder(vehicle_id=sample_vehicle.id, user_id=test_user.id, title='Inspection',
                                reminder_type='custom', due_date=date.today() + timedelta(days=245)))
        db.session.commit()
        html = auth_client.get('/dashboard').get_data(as_text=True)
        assert 'Nothing due in the next 30 days' in html
        assert 'ds-badge--success">All good' in html

    def test_vehicle_row_reads_the_odometer_as_text(self, auth_client, test_user, sample_vehicle):
        _spend(sample_vehicle, test_user, date.today(), fuel=30)
        html = auth_client.get('/dashboard').get_data(as_text=True)
        assert 'class="dashboard-odometer"' in html
        assert 'ds-odometer__digit' not in html
        assert 'ds-swatch' not in html


def _price(user, station_name, price, days_ago=1, fuel_type='petrol'):
    station = FuelStation.query.filter_by(user_id=user.id, name=station_name).first()
    if station is None:
        station = FuelStation(user_id=user.id, name=station_name)
        db.session.add(station)
        db.session.flush()
    db.session.add(FuelPriceHistory(station_id=station.id, user_id=user.id, fuel_type=fuel_type,
                                    price_per_unit=price, date=date.today() - timedelta(days=days_ago)))
    db.session.commit()


class TestDashboardCheapestFuel:
    def test_hidden_without_prices(self, auth_client, sample_vehicle):
        html = auth_client.get('/dashboard').get_data(as_text=True)
        assert 'Cheapest Fuel' not in html
        assert 'No price data yet' not in html

    def test_hidden_with_one_station(self, auth_client, test_user, sample_vehicle):
        _price(test_user, 'Only One', 1.50)
        assert 'Cheapest Fuel' not in auth_client.get('/dashboard').get_data(as_text=True)

    def test_hidden_when_every_station_charges_the_same(self, auth_client, test_user, sample_vehicle):
        # A state-set price, as in Bangladesh: there is no cheapest station.
        _price(test_user, 'Padma', 122.0)
        _price(test_user, 'Meghna', 122.0)
        _price(test_user, 'Jamuna', 122.0)
        assert 'Cheapest Fuel' not in auth_client.get('/dashboard').get_data(as_text=True)

    def test_shown_when_stations_differ(self, auth_client, test_user, sample_vehicle):
        _price(test_user, 'Dear', 1.60)
        _price(test_user, 'Cheap', 1.45)
        html = auth_client.get('/dashboard').get_data(as_text=True)
        assert 'Cheapest Fuel' in html
        assert '1.450' in html and 'Cheap · ' in html

    def test_a_station_counts_with_its_latest_price(self, auth_client, test_user, sample_vehicle):
        _price(test_user, 'A', 1.40, days_ago=20)
        _price(test_user, 'A', 1.50, days_ago=2)
        _price(test_user, 'B', 1.50, days_ago=1)
        assert 'Cheapest Fuel' not in auth_client.get('/dashboard').get_data(as_text=True)

    def test_old_prices_do_not_count(self, auth_client, test_user, sample_vehicle):
        _price(test_user, 'Old', 1.20, days_ago=90)
        _price(test_user, 'New', 1.50, days_ago=1)
        assert 'Cheapest Fuel' not in auth_client.get('/dashboard').get_data(as_text=True)

    def test_fuels_are_not_compared_with_each_other(self, auth_client, test_user, sample_vehicle):
        _price(test_user, 'A', 1.50, fuel_type='petrol')
        _price(test_user, 'B', 1.70, fuel_type='diesel')
        assert 'Cheapest Fuel' not in auth_client.get('/dashboard').get_data(as_text=True)

    def test_hidden_with_stations_off_in_the_menu(self, auth_client, test_user, sample_vehicle):
        _price(test_user, 'Dear', 1.60)
        _price(test_user, 'Cheap', 1.45)
        test_user.show_menu_stations = False
        db.session.commit()
        assert 'Cheapest Fuel' not in auth_client.get('/dashboard').get_data(as_text=True)

    def test_another_users_prices_stay_out(self, auth_client, test_user, sample_vehicle):
        other = User(username='neighbour', email='neighbour@example.com')
        other.set_password('Password123')
        db.session.add(other)
        db.session.commit()
        _price(other, 'Their Dear', 1.60)
        _price(other, 'Their Cheap', 1.10)
        _price(test_user, 'Mine', 1.50)
        assert 'Cheapest Fuel' not in auth_client.get('/dashboard').get_data(as_text=True)


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
