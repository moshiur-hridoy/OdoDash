"""Guards the dark-mode background classes in the templates.

An earlier mechanical pass paired each light background with a dark one
(`bg-white` -> `bg-white dark:bg-gray-800`, `bg-gray-50` -> `bg-gray-50
dark:bg-gray-700`) but also matched inside variant-prefixed classes. That
turned `hover:bg-gray-50` into `hover:bg-gray-50 dark:bg-gray-700`, so table
rows and list items in dark mode sat permanently highlighted with no hover
feedback, and `after:bg-white` on toggle knobs painted the toggle track the
same colour as the card behind it.
"""
import re
from pathlib import Path

import pytest

TEMPLATES = Path(__file__).resolve().parent.parent / 'app' / 'templates'

_CLASS_ATTR = re.compile(r'class="([^"]*)"')
# Jinja tags split a class attribute into segments; classes in different
# `{% if %}` branches never apply together, so each segment is checked alone.
_JINJA = re.compile(r'\{%.*?%\}|\{\{.*?\}\}')
_PLAIN_DARK_BG = re.compile(r'^dark:bg-(?:white|black|[a-z]+-\d+(?:/\d+)?)$')
# The fingerprint of the bad pass: a variant-prefixed light background
# immediately followed by the plain dark background the pass appended to it.
_LEAKED_PAIR = re.compile(r'(?<![\w:-])([a-z-]+):(bg-white|bg-gray-50) (dark:bg-[a-z]+-\d+)\b')


def _class_segments():
    for path in sorted(TEMPLATES.rglob('*.html')):
        rel = path.relative_to(TEMPLATES)
        for lineno, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            for attr in _CLASS_ATTR.findall(line):
                for segment in _JINJA.split(attr):
                    if segment.strip():
                        yield f'{rel}:{lineno}', segment


def test_no_dark_background_leaked_from_a_variant_class():
    offenders = [
        f'{where}: {match.group(0)}'
        for where, segment in _class_segments()
        for match in _LEAKED_PAIR.finditer(segment)
    ]
    assert not offenders, (
        'A variant-prefixed background is followed by a plain dark background; '
        'it was probably meant to be dark:<variant>:bg-...\n' + '\n'.join(offenders)
    )


def test_each_element_has_one_dark_background():
    offenders = []
    for where, segment in _class_segments():
        dark_bgs = [tok for tok in segment.split() if _PLAIN_DARK_BG.match(tok)]
        if len(dark_bgs) > 1:
            offenders.append(f'{where}: {" ".join(dark_bgs)}')
    assert not offenders, (
        'Conflicting dark backgrounds on one element; only the one Tailwind '
        'happens to emit last applies:\n' + '\n'.join(offenders)
    )


# The list rows that had this check (fuel/index.html, reminders/_reminder_row.html)
# moved to the design system, whose rows take their hover colour from the
# --ds-* tokens in both themes.
