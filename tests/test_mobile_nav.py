"""Phone/tablet bottom tab bar, quick-add sheet and More sheet."""
import re

from app import db
from app.models import ROLE_CONTRIBUTOR, ROLE_VIEWER


def _section(html, element_id):
    """Return the markup of the sheet with the given id."""
    start = html.index(f'id="{element_id}"')
    end = html.find('<div class="sheet"', start + 1)
    return html[start:end if end != -1 else len(html)]


def _tabbar(html):
    start = html.index('<nav class="tabbar')
    return html[start:html.index('</nav>', start)]


class TestMobileNav:
    def test_tab_bar_replaces_hamburger_menu(self, auth_client):
        html = auth_client.get('/dashboard').get_data(as_text=True)
        assert 'class="tabbar' in html
        assert 'id="mobile-menu"' not in html
        assert 'viewport-fit=cover' in html

    def test_default_tabs_are_dashboard_fuel_and_expenses(self, auth_client):
        tabbar = _tabbar(auth_client.get('/dashboard').get_data(as_text=True))
        hrefs = re.findall(r'href="([^"]+)"', tabbar)
        assert hrefs == ['/dashboard', '/fuel/', '/expenses/']
        assert 'data-sheet-open="sheet-add"' in tabbar
        assert 'data-sheet-open="sheet-more"' in tabbar

    def test_more_sheet_lists_remaining_sections(self, auth_client):
        more = _section(auth_client.get('/dashboard').get_data(as_text=True), 'sheet-more')
        assert '/vehicles/' in more
        assert '/maintenance/' in more
        assert '/fuel/' not in more  # already a tab
        assert '/auth/settings' in more
        assert '/auth/logout' in more

    def test_hidden_menu_sections_are_left_out(self, auth_client, test_user):
        test_user.show_menu_fuel = False
        test_user.show_menu_maintenance = False
        db.session.commit()
        html = auth_client.get('/dashboard').get_data(as_text=True)
        hrefs = re.findall(r'href="([^"]+)"', _tabbar(html))
        assert hrefs == ['/dashboard', '/expenses/', '/vehicles/']
        assert '/maintenance/' not in _section(html, 'sheet-more')
        assert '/fuel/quick' not in _section(html, 'sheet-add')

    def test_contributor_can_only_quick_add_fuel_and_charging(self, auth_client, test_user):
        test_user.role = ROLE_CONTRIBUTOR
        db.session.commit()
        add = _section(auth_client.get('/dashboard').get_data(as_text=True), 'sheet-add')
        assert '/fuel/quick' in add
        assert '/charging/new' in add
        assert '/expenses/new' not in add
        assert '/reminders/new' not in add

    def test_viewer_gets_no_quick_add_button(self, auth_client, test_user):
        test_user.role = ROLE_VIEWER
        db.session.commit()
        html = auth_client.get('/dashboard').get_data(as_text=True)
        assert 'data-sheet-open="sheet-add"' not in html
        assert 'id="sheet-add"' not in html

    def test_more_tab_is_active_on_a_more_section(self, auth_client):
        tabbar = _tabbar(auth_client.get('/maintenance/').get_data(as_text=True))
        assert re.search(r'class="tabbar__tab is-active" data-sheet-open="sheet-more"', tabbar)
