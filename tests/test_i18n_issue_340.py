"""Reproduces #340: more hardcoded / uncatalogued strings surviving the
#328/#310 sweep.

Two distinct failure modes, same as #328:

(a) literals never passed through gettext() at all (settings.html import
    cards, the reminders due-date line, the vehicle timeline titles in
    main.py) -- these can never be translated no matter the catalogue.
(b) strings that *are* wrapped in `_()` but whose msgid never made it into
    the shipped catalogues, so every non-English user just sees the English
    source text (Role, Photos, Restore May Backup, the Tires page).
"""
import os
import re

from flask_babel import force_locale, gettext

TEMPLATES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'app', 'templates',
)


def _read(*parts):
    with open(os.path.join(*parts), encoding='utf-8') as f:
        return f.read()


def _settings_source():
    return _read(TEMPLATES_DIR, 'auth', 'settings.html')


def _reminder_row_source():
    return _read(TEMPLATES_DIR, 'reminders', '_reminder_row.html')


def _main_routes_source():
    return _read(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'app', 'routes', 'main.py',
    )


class TestImportCardsUseGettext:
    """The whole "Import Data" card on the Integrations tab is a mix of
    gettext() calls (the header) and bare literals (every provider row) --
    the row descriptions and the "Import"/"Soon" buttons never reach a
    translator (#340)."""

    def _card_block(self):
        source = _settings_source()
        start = source.index('Import Data')
        end = source.index('Export Data')
        return source[start:end]

    def test_hammond_description_uses_gettext(self):
        block = self._card_block()
        match = re.search(
            r'Hammond</h3>\s*<p[^>]*>(.*?)</p>', block, re.DOTALL)
        assert match is not None, "Hammond import row not found — has it moved?"
        assert '_(' in match.group(1), (
            "the Hammond import description is a bare literal, so it is "
            "never translated (#340)"
        )

    def test_clarkson_description_uses_gettext(self):
        block = self._card_block()
        match = re.search(
            r'Clarkson</h3>\s*<p[^>]*>(.*?)</p>', block, re.DOTALL)
        assert match is not None, "Clarkson import row not found — has it moved?"
        assert '_(' in match.group(1), (
            "the Clarkson import description is a bare literal, so it is "
            "never translated (#340)"
        )

    def test_fuelly_description_uses_gettext(self):
        block = self._card_block()
        match = re.search(
            r'Fuelly</h3>\s*<p[^>]*>(.*?)</p>', block, re.DOTALL)
        assert match is not None, "Fuelly import row not found — has it moved?"
        assert '_(' in match.group(1), (
            "the Fuelly import description is a bare literal, so it is "
            "never translated (#340)"
        )

    def test_drivvo_description_uses_gettext(self):
        block = self._card_block()
        match = re.search(
            r'Drivvo</h3>\s*<p[^>]*>(.*?)</p>', block, re.DOTALL)
        assert match is not None, "Drivvo import row not found — has it moved?"
        assert '_(' in match.group(1), (
            "the Drivvo import description is a bare literal, so it is "
            "never translated (#340)"
        )

    def test_csv_import_description_uses_gettext(self):
        block = self._card_block()
        match = re.search(
            r'CSV Import.{0,8}</h3>\s*<p[^>]*>(.*?)</p>', block, re.DOTALL)
        assert match is not None, "CSV Import row not found — has it moved?"
        assert '_(' in match.group(1), (
            "the CSV Import description is a bare literal, so it is never "
            "translated (#340)"
        )

    def test_import_buttons_use_gettext(self):
        block = self._card_block()
        # Four import controls (Hammond, Clarkson, Fuelly, CSV) carry an
        # 'Import' label; each must reach gettext, none may stay a literal.
        bare = re.findall(r'>\s*Import\s*<', block)
        wrapped = re.findall(r"_\(\s*['\"]Import['\"]\s*\)", block)
        assert len(bare) + len(wrapped) >= 4, (
            "the Import button labels were not found — have they moved?"
        )
        assert bare == [], (
            f"found {len(bare)} 'Import' button labels not wrapped in "
            f"gettext, so they are never translated (#340)"
        )

    def test_soon_button_uses_gettext(self):
        block = self._card_block()
        assert re.search(r"(>\s*Soon\s*<|_\(\s*['\"]Soon['\"]\s*\))",
                         block) is not None, (
            "the disabled Drivvo 'Soon' button not found — has it moved?"
        )
        assert re.search(r"_\(\s*['\"]Soon['\"]\s*\)", block) is not None, (
            "the disabled Drivvo 'Soon' button is a bare literal, so it is "
            "never translated (#340)"
        )


class TestReminderDueDateUsesGettext:
    """Every branch of the reminder row's due-date caption is a bare
    literal: 'Completed', 'Due today', 'Due tomorrow', 'N days overdue' and
    'In N days' all skip gettext() entirely (#340)."""

    def test_in_n_days_uses_gettext(self):
        source = _reminder_row_source()
        assert '_(' in source, "reminders/_reminder_row.html has no gettext calls at all"
        caption = re.search(
            r'days_until_due\(\) == 1 -?%\}(.*?)\{%-? endif -?%\}',
            source, re.DOTALL)
        assert caption is not None, (
            "the reminder due-date caption not found — has it moved?"
        )
        match = re.search(r'\{%-? else -?%\}(.*)', caption.group(1), re.DOTALL)
        assert match is not None
        assert '_(' in match.group(1), (
            "the 'In {{ reminder.days_until_due() }} days' caption is a "
            "bare literal, so it never translates (#340)"
        )

    def test_due_today_and_tomorrow_use_gettext(self):
        source = _reminder_row_source()
        assert re.search(r"_\(\s*['\"]Due today['\"]\s*\)", source), (
            "'Due today' is a bare literal in the reminder row (#340)"
        )
        assert re.search(r"_\(\s*['\"]Due tomorrow['\"]\s*\)", source), (
            "'Due tomorrow' is a bare literal in the reminder row (#340)"
        )


class TestTimelineTitlesUseGettext:
    """The vehicle timeline builds its event titles as plain f-strings in
    main.py -- 'Fuel: N L' and 'Charging: N kWh' never pass through
    gettext(), so the labels are always English regardless of the viewer's
    language (#340)."""

    def test_main_routes_imports_gettext(self):
        source = _main_routes_source()
        assert 'gettext' in source, (
            "app/routes/main.py never imports flask_babel.gettext, so none "
            "of its strings (including the timeline titles) can be "
            "translated (#340)"
        )

    def test_fuel_timeline_title_uses_gettext(self):
        source = _main_routes_source()
        match = re.search(r"'title': \(?(.*?)\s*if log\.volume", source,
                          re.DOTALL)
        assert match is not None, "fuel timeline title not found — has it moved?"
        assert 'gettext(' in match.group(1) or '_(' in match.group(1), (
            "the 'Fuel: {volume} L' timeline title is a bare f-string, so "
            "it is never translated (#340)"
        )

    def test_charging_timeline_title_uses_gettext(self):
        source = _main_routes_source()
        match = re.search(r"'title': \(?(.*?)\s*if session\.kwh_added",
                          source, re.DOTALL)
        assert match is not None, "charging timeline title not found — has it moved?"
        assert 'gettext(' in match.group(1) or '_(' in match.group(1), (
            "the 'Charging: {kwh} kWh' timeline title is a bare f-string, "
            "so it is never translated (#340)"
        )


class TestWrappedButUncataloguedStrings:
    """These are already passed through gettext() in the templates, but the
    msgid never reached the shipped .po/.mo catalogues, so every non-English
    user still sees the English source text -- the same "incremental
    messages.pot update" gap as #328 (#340)."""

    def _missing_in(self, code, msgids):
        with force_locale(code):
            return [msgid for msgid in msgids if gettext(msgid) == msgid]

    def test_settings_strings_are_catalogued_in_hungarian(self, app):
        msgids = [
            'Role',
            'Restore May Backup',
            'Restore a May backup, or import your data from other fuel '
            'tracking applications',
        ]
        missing = self._missing_in('hu', msgids)
        assert missing == [], (
            f"settings.html strings with no Hungarian catalogue entry: "
            f"{missing} (#340)"
        )

    def test_dashboard_photo_strings_are_catalogued_in_hungarian(self, app):
        msgids = ['Photos', 'No photos yet.', 'PDF + Receipts']
        missing = self._missing_in('hu', msgids)
        assert missing == [], (
            f"vehicle dashboard strings with no Hungarian catalogue entry: "
            f"{missing} (#340)"
        )

    def test_tires_strings_are_catalogued_in_hungarian(self, app):
        msgids = ['Add Tire Set', 'Fitted', 'Retired', 'In storage']
        missing = self._missing_in('hu', msgids)
        assert missing == [], (
            f"Tires page strings with no Hungarian catalogue entry: "
            f"{missing} (#340)"
        )
