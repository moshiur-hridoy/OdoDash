"""The desktop sidebar, phone top bar and page frame in base.html."""
import re
from pathlib import Path

from app import db
from app.models import ROLE_VIEWER

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / 'app' / 'templates'


def _sidebar(html):
    start = html.index('<aside class="ds-side"')
    return html[start:html.index('</aside>', start)]


def _nav_hrefs(sidebar):
    nav = sidebar[sidebar.index('<nav class="ds-nav"'):sidebar.index('</nav>')]
    return re.findall(r'href="([^"]+)"', nav)


class TestSidebar:
    def test_lists_every_section_in_order(self, auth_client):
        sidebar = _sidebar(auth_client.get('/dashboard').get_data(as_text=True))
        assert _nav_hrefs(sidebar) == [
            '/dashboard', '/vehicles/', '/fuel/', '/charging/', '/expenses/', '/reminders/',
            '/trips/', '/maintenance/', '/recurring/', '/documents/', '/stations/',
            '/allowance/', '/tires/', '/notes/',
        ]

    def test_marks_the_current_section(self, auth_client):
        sidebar = _sidebar(auth_client.get('/fuel/').get_data(as_text=True))
        current = re.findall(r'<a href="([^"]+)" class="ds-nav__item is-active" aria-current="page">', sidebar)
        assert current == ['/fuel/']

    def test_hidden_sections_are_left_out(self, auth_client, test_user):
        test_user.show_menu_trips = False
        test_user.show_menu_notes = False
        db.session.commit()
        hrefs = _nav_hrefs(_sidebar(auth_client.get('/dashboard').get_data(as_text=True)))
        assert '/trips/' not in hrefs and '/notes/' not in hrefs
        assert '/fuel/' in hrefs

    def test_more_heading_only_when_something_sits_under_it(self, auth_client, test_user):
        assert 'ds-nav__heading' in _sidebar(auth_client.get('/dashboard').get_data(as_text=True))
        for key in ('maintenance', 'recurring', 'documents', 'stations',
                    'allowance', 'tires', 'notes'):
            setattr(test_user, f'show_menu_{key}', False)
        db.session.commit()
        assert 'ds-nav__heading' not in _sidebar(auth_client.get('/dashboard').get_data(as_text=True))

    def test_account_controls(self, auth_client):
        sidebar = _sidebar(auth_client.get('/dashboard').get_data(as_text=True))
        assert 'id="theme-toggle"' in sidebar
        assert 'href="/auth/settings"' in sidebar
        assert 'href="/auth/logout"' in sidebar
        assert 'href="/search/"' in sidebar
        assert 'testuser' in sidebar

    def test_quick_fuel_follows_the_setting_and_write_access(self, auth_client, test_user):
        test_user.show_quick_entry = True
        db.session.commit()
        assert 'data-quick-fuel' in _sidebar(auth_client.get('/dashboard').get_data(as_text=True))
        test_user.role = ROLE_VIEWER
        db.session.commit()
        assert 'data-quick-fuel' not in _sidebar(auth_client.get('/dashboard').get_data(as_text=True))


def test_phone_top_bar_keeps_search_and_safe_area(auth_client):
    html = auth_client.get('/dashboard').get_data(as_text=True)
    start = html.index('<header class="mobile-topbar ds-topbar"')
    topbar = html[start:html.index('</header>', start)]
    assert 'aria-label="Search"' in topbar
    assert '.mobile-topbar { padding-top: env(safe-area-inset-top); }' in html


def test_shell_sides_are_logical_so_rtl_mirrors_it():
    """inset-inline-start / padding-inline-start put the sidebar on the right
    in a right-to-left language without a separate RTL stylesheet."""
    css = (ROOT / 'app' / 'static' / 'css' / 'src' / 'app.css').read_text(encoding='utf-8')
    shell = css[css.index('/* ---- App shell'):css.index('@tailwind utilities;')]
    assert 'inset-inline-start: 0' in shell
    assert 'padding-inline-start: var(--ds-sidebar-width)' in shell
    assert not re.search(r'(?<![-\w])(left|right)\s*:', shell)
    assert not re.search(r'(padding|margin|border)-(left|right)\b', shell)


def test_legacy_tokens_follow_the_design_system():
    base = (TEMPLATES / 'base.html').read_text(encoding='utf-8')
    for legacy, ds in (('background', 'bg'), ('surface', 'surface'), ('border', 'border'),
                       ('text', 'text'), ('text-muted', 'text-muted')):
        assert f'--color-{legacy}: var(--ds-{ds},' in base


def test_every_icon_the_shell_uses_exists():
    icons = (TEMPLATES / 'components' / 'icons.html').read_text(encoding='utf-8')
    known = set(re.findall(r"^\s+'([a-z-]+)': '", icons, re.M))
    used = set()
    for path in (TEMPLATES / 'base.html', TEMPLATES / 'partials' / 'mobile_nav.html'):
        source = path.read_text(encoding='utf-8')
        used |= set(re.findall(r"\bicon\('([a-z-]+)'", source))
        used |= set(re.findall(r"ICONS\['([a-z-]+)'\]", source))
        # nav_sections tuples: (key, endpoint, label, active, '<icon>', primary)
        used |= set(re.findall(r", '([a-z-]+)', (?:True|False)\),", source))
    assert len(used) > 15, 'scanner found too few icon references'
    assert used <= known, f'unknown icons: {sorted(used - known)}'


class TestRuntimeFallback:
    def test_design_system_css_goes_to_the_runtime_when_nothing_was_built(self, auth_client, app, tmp_path, monkeypatch):
        static = tmp_path / 'static'
        (static / 'css' / 'src').mkdir(parents=True)
        (static / 'css' / 'src' / 'app.css').write_text(
            '@tailwind base;\n@font-face { src: url(../fonts/a.woff2); }\n.ds-side { display: none; }\n@tailwind utilities;\n')
        monkeypatch.setattr(app, 'static_folder', str(static))
        html = auth_client.get('/dashboard').get_data(as_text=True)
        block = re.search(r'<style type="text/tailwindcss">(.*?)</style>', html, re.S).group(1)
        assert '.ds-side { display: none; }' in block
        assert '@tailwind' not in block  # the runtime adds its own directives
        assert 'url(/static/fonts/a.woff2)' in block

    def test_not_inlined_when_the_stylesheet_is_built(self, auth_client, app, tmp_path, monkeypatch):
        static = tmp_path / 'static'
        (static / 'css' / 'src').mkdir(parents=True)
        (static / 'css' / 'app.css').write_text('body{}')
        (static / 'css' / 'src' / 'app.css').write_text('.ds-side {}')
        monkeypatch.setattr(app, 'static_folder', str(static))
        html = auth_client.get('/dashboard').get_data(as_text=True)
        assert 'text/tailwindcss' not in html
