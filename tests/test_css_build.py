"""The compiled Tailwind stylesheet and its in-browser fallback.

The image ships app/static/css/app.css, built by scripts/build_css.py; a
checkout that has not run the build falls back to the Tailwind runtime script.
Both paths have to keep rendering every page.
"""
import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / 'app' / 'templates'


@pytest.fixture
def static_dir(app, tmp_path, monkeypatch):
    """Point the app at an empty static folder so each test chooses whether
    the compiled stylesheet exists, without touching the real one."""
    monkeypatch.setattr(app, 'static_folder', str(tmp_path))
    return tmp_path


def _built(static_dir):
    css = static_dir / 'css' / 'app.css'
    css.parent.mkdir(parents=True, exist_ok=True)
    css.write_text('body{}')
    return css


def test_compiled_stylesheet_replaces_the_runtime(auth_client, static_dir):
    _built(static_dir)
    html = auth_client.get('/dashboard').get_data(as_text=True)
    assert re.search(r'<link rel="stylesheet" href="/static/css/app\.css\?v=\d+">', html)
    assert 'tailwind.config =' not in html
    assert 'vendor/tailwindcss.js' not in html


def test_runtime_is_used_when_nothing_was_built(auth_client, static_dir):
    html = auth_client.get('/dashboard').get_data(as_text=True)
    assert 'static/css/app.css' not in html
    assert 'tailwind.config =' in html
    assert 'vendor/tailwindcss.js' in html


def test_compiled_stylesheet_loads_last_in_head(auth_client, static_dir):
    """The runtime appended its <style> to the end of <head>, so its utilities
    won ties with the inline styles and premium.css. The stylesheet that
    replaces it has to sit in the same place to keep every page unchanged."""
    _built(static_dir)
    html = auth_client.get('/dashboard').get_data(as_text=True)
    head = html[:html.index('</head>')]
    assert head.rindex('css/app.css') > head.rindex('premium.css')
    assert head.rindex('css/app.css') > head.rindex('</style>')


def test_login_page_gets_the_stylesheet_too(client, static_dir):
    _built(static_dir)
    html = client.get('/auth/login', follow_redirects=True).get_data(as_text=True)
    assert 'static/css/app.css' in html


def test_accent_palette_exposes_rgb_channels():
    """tailwind.config.js builds primary-* from --primary-N-rgb, which keeps
    opacity modifiers such as bg-primary-900/30 working."""
    base = (TEMPLATES / 'base.html').read_text(encoding='utf-8')
    config = (ROOT / 'tailwind.config.js').read_text(encoding='utf-8')
    assert '--primary-${key}-rgb' in base
    assert 'rgb(var(--primary-${s}-rgb) / <alpha-value>)' in config


# A class name glued to template output (`bg-{{ tone }}-100`, `text-{% ... %}`)
# only exists once the page renders, so the build never sees it and the class
# silently has no CSS. Spell each class out in full instead. A whole class
# chosen by a tag (`{% if a %}font-medium{% endif %}`) is fine: the build sees
# `font-medium` intact. (Hand-written BEM modifiers such as `toast--{{ kind }}`
# are styled outside Tailwind and are not matched.)
_CLASS_ATTR = re.compile(r'class="([^"]*)"', re.S)
_GLUED = re.compile(r'\w-(?:\{\{|\{%)|(?:\}\}|%\})-\w')


def test_no_class_name_is_assembled_at_render_time():
    offenders = []
    for path in sorted(TEMPLATES.rglob('*.html')):
        source = path.read_text(encoding='utf-8')
        for match in _CLASS_ATTR.finditer(source):
            glued = _GLUED.search(match.group(1))
            if glued:
                line = source.count('\n', 0, match.start()) + 1
                offenders.append(f'{path.relative_to(TEMPLATES)}:{line}: …{glued.group(0)}…')
    assert not offenders, (
        'Class names built from template output are invisible to the Tailwind '
        'build:\n' + '\n'.join(offenders)
    )


def test_glued_class_scanner_catches_both_forms():
    assert _GLUED.search('px-2 bg-{{ tone }}-100')
    assert _GLUED.search('text-{% if ok %}green{% else %}red{% endif %}-700')
    assert not _GLUED.search('px-2 {{ "bg-red-100" if bad }} rounded')
    assert _GLUED.search('ring-{{ n }}')
    assert not _GLUED.search('{% if active %}font-medium{% endif %} text-sm')
    assert not _GLUED.search('toast toast--{{ kind }}')


def test_design_system_classes_are_never_purged():
    """The component macros compose class names (`'ds-btn--' ~ variant`,
    `ds-badge--{{ tone }}`) that the build cannot see. Inside a Tailwind
    @layer they would be dropped and the components would render unstyled,
    so the .ds- rules stay plain CSS, placed before the utilities so a
    utility still wins a tie."""
    source = (ROOT / 'app' / 'static' / 'css' / 'src' / 'app.css').read_text(encoding='utf-8')
    assert '@layer components {' not in source
    assert '@layer utilities {' not in source
    assert source.index('.ds-btn {') < source.index('@tailwind utilities;')


def test_build_script_covers_the_image_platforms():
    spec = importlib.util.spec_from_file_location('build_css', ROOT / 'scripts' / 'build_css.py')
    build_css = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build_css)
    for platform in ('linux-x64', 'linux-arm64'):
        assert re.fullmatch(r'[0-9a-f]{64}', build_css.CHECKSUMS[platform])
