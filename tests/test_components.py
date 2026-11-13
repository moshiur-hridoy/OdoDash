"""Design-system components (templates/components/) and the /design page."""
import re
from pathlib import Path

import pytest
from flask import render_template_string

from app import db

TEMPLATES = Path(__file__).resolve().parent.parent / 'app' / 'templates'


def render(app, source, **context):
    with app.test_request_context():
        return render_template_string(
            "{% from 'components/ui.html' import page_header, button, card, stat, badge, "
            "segmented, split_bar, attention, odometer, empty_state, field %}" + source,
            **context,
        )


class TestButton:
    def test_link_when_given_an_href(self, app):
        html = render(app, "{{ button('Add', href='/fuel/new', icon_name='plus') }}")
        assert html.startswith('<a href="/fuel/new" class="ds-btn ds-btn--primary"')
        assert '<span>Add</span>' in html and '<svg' in html

    def test_button_otherwise(self, app):
        html = render(app, "{{ button('Save', type='submit', variant='secondary', size='sm') }}")
        assert html.startswith('<button type="submit" class="ds-btn ds-btn--secondary ds-btn--sm"')

    def test_icon_only_keeps_an_accessible_name(self, app):
        html = render(app, "{{ button('Delete', icon_name='trash', icon_only=True) }}")
        assert 'ds-btn--icon' in html
        assert '<span class="ds-sr-only">Delete</span>' in html
        assert 'title="Delete"' in html

    def test_extra_attributes_are_escaped(self, app):
        html = render(app, "{{ button('Go', attrs={'hx-get': '/x?a=1&b=2', 'data-confirm': q}) }}",
                      q='Sure? "yes"')
        assert 'hx-get="/x?a=1&amp;b=2"' in html
        assert 'data-confirm="Sure? &#34;yes&#34;"' in html

    def test_disabled_link_leaves_the_tab_order(self, app):
        html = render(app, "{{ button('Go', href='/x', disabled=True) }}")
        assert 'aria-disabled="true"' in html and 'tabindex="-1"' in html


class TestOdometer:
    def test_pads_and_marks_digits(self, app):
        html = render(app, "{{ odometer(8627) }}")
        digits = re.findall(r'ds-odometer__digit([^"]*)"[^>]*>(\d)<', html)
        assert [d for _, d in digits] == list('008627')
        assert digits[0][0] == digits[1][0] == ' ds-odometer__digit--off'
        assert digits[-1][0] == ' ds-odometer__digit--last'
        assert 'aria-label="8,627 km"' in html

    def test_long_readings_are_not_truncated(self, app):
        html = render(app, "{{ odometer(1234567) }}")
        assert ''.join(re.findall(r'>(\d)<', html)) == '1234567'

    def test_custom_label_and_unit(self, app):
        html = render(app, "{{ odometer(1240, unit='h', label='Engine hours 1,240') }}")
        assert 'aria-label="Engine hours 1,240"' in html and '>h<' in html


class TestOtherComponents:
    def test_card_header_and_body(self, app):
        html = render(app, "{% call card('Recent', action_label='View all', action_href='/x', flush=True) %}BODY{% endcall %}")
        assert 'class="ds-card ds-card--flush"' in html
        assert '<h2 class="ds-card__title">Recent</h2>' in html
        assert '<a class="ds-card__action" href="/x">View all</a>' in html
        assert '<div class="ds-card__body">BODY</div>' in html

    def test_card_without_body_or_header(self, app):
        html = render(app, "{{ card() }}")
        assert 'ds-card__header' not in html and 'ds-card__body' not in html

    def test_page_header_actions_only_when_given(self, app):
        assert 'ds-page-header__actions' not in render(app, "{{ page_header('Fuel') }}")
        html = render(app, "{% call page_header('Fuel', subtitle='All fill-ups') %}ACT{% endcall %}")
        assert '<h1 class="ds-page-header__title">Fuel</h1>' in html
        assert '<div class="ds-page-header__actions">ACT</div>' in html

    def test_stat_hero_with_badge_and_note(self, app):
        html = render(app, "{{ stat('Spent', '18,420', unit='BDT', note='Less', note_tone='success', hero=True, badge_label='-12%', badge_tone='success') }}")
        assert 'ds-stat ds-stat--hero' in html
        assert '<span class="ds-stat__unit">BDT</span>' in html
        assert 'ds-badge ds-badge--success">-12%' in html
        assert 'ds-stat__note ds-stat__note--success' in html

    def test_segmented_marks_the_current_item(self, app):
        html = render(app, "{{ segmented([{'label': 'Month', 'href': '/m', 'current': True}, {'label': 'Year', 'href': '/y'}], 'Period') }}")
        assert 'aria-label="Period"' in html
        assert '<a class="ds-segmented__item" href="/m" aria-current="page">Month</a>' in html
        assert '<a class="ds-segmented__item" href="/y">Year</a>' in html

    def test_split_bar_describes_itself_and_skips_empty_segments(self, app):
        html = render(app, "{{ split_bar([{'label': 'Fuel', 'value': 70, 'display': '70%', 'series': 'accent'}, {'label': 'Charging', 'value': 0, 'display': '0%', 'series': 'charging'}], 'Spending') }}")
        assert 'aria-label="Spending: Fuel 70%, Charging 0%"' in html
        assert html.count('ds-split__segment') == 1
        assert html.count('ds-legend__item') == 2

    def test_attention_tone_and_action(self, app):
        html = render(app, "{{ attention('Insurance expired', 'Corolla', 'danger', 'alert', 'Renew', '/r') }}")
        assert html.startswith('<li class="ds-attention ds-attention--danger">')
        assert '<a class="ds-attention__action" href="/r">Renew</a>' in html

    def test_empty_state_offers_the_first_step(self, app):
        html = render(app, "{{ empty_state('No logs', 'Add one', 'fuel', 'Add fuel log', '/fuel/new') }}")
        assert '<p class="ds-empty__title">No logs</p>' in html
        assert 'href="/fuel/new"' in html

    def test_field_links_label_help_and_error(self, app):
        html = render(app, "{% call field('Odometer', 'odo', help='In km', error='Required', required=True) %}<input id=\"odo\" class=\"ds-control\">{% endcall %}")
        assert '<label class="ds-field__label" for="odo">' in html
        assert 'id="odo-help"' in html and 'id="odo-error"' in html
        assert 'ds-field__required' in html


def test_every_icon_used_by_the_components_exists():
    icons = (TEMPLATES / 'components' / 'icons.html').read_text(encoding='utf-8')
    known = set(re.findall(r"^\s+'([a-z-]+)': '", icons, re.M))
    used = set()
    for path in [TEMPLATES / 'components' / 'ui.html', TEMPLATES / 'design' / 'index.html']:
        source = path.read_text(encoding='utf-8')
        used |= set(re.findall(r"icon_name='([a-z-]+)'", source))
        used |= set(re.findall(r"\{\{ icon\('([a-z-]+)'", source))
        # attention(..., tone, '<icon>', ...) and empty_state(..., '<icon>', ...)
        used |= set(re.findall(r"attention\('[^']*', (?:'[^']*'|None), '[a-z]+', '([a-z-]+)'", source))
        used |= set(re.findall(r"empty_state\('[^']*', '[^']*', '([a-z-]+)'", source))
    assert used, 'scanner found no icon references'
    assert used <= known, f'unknown icons: {sorted(used - known)}'


def test_base_form_rules_leave_design_system_controls_alone():
    """base.html styles every bare form control; .ds-control fields get their
    look from app.css instead, so each of those rules must exclude them."""
    base = (TEMPLATES / 'base.html').read_text(encoding='utf-8')
    selectors = re.findall(r'form (input|select|textarea)([^\s,{]*)', base)
    assert selectors
    for element, rest in selectors:
        # :where() keeps the exclusion at zero specificity, so it cannot change
        # which rule wins for any control that existed before.
        assert rest.startswith(':where(:not(.ds-control))'), f'form {element}{rest}'


class TestDesignPage:
    def test_admin_sees_every_section(self, admin_client):
        resp = admin_client.get('/design/')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        for section in ('dashboard', 'tokens', 'buttons', 'badges', 'stats', 'controls',
                        'attention', 'odometer', 'table', 'forms', 'empty'):
            assert f'id="{section}"' in html

    def test_other_users_are_refused(self, auth_client):
        assert auth_client.get('/design/').status_code == 403

    def test_needs_a_login(self, client):
        resp = client.get('/design/')
        assert resp.status_code in (302, 401)
