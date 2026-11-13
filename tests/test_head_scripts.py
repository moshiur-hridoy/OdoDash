"""base.html renders `{% block extra_scripts %}` inside <head>, before the page
body exists. An inline script there that looks up elements straight away finds
nothing and throws, so the form behind it silently stops working (the expense
form's category switch did exactly this). Such scripts must wait for
DOMContentLoaded."""
import pathlib
import re

TEMPLATES = pathlib.Path(__file__).resolve().parent.parent / 'app' / 'templates'
BLOCK = re.compile(r'\{%-?\s*block extra_scripts\s*-?%\}(.*?)\{%-?\s*endblock', re.S)
INLINE = re.compile(r'<script>(.*?)</script>', re.S)
DOM = re.compile(r'getElementById|querySelector')


def test_head_scripts_wait_for_the_page():
    offenders = []
    for path in TEMPLATES.rglob('*.html'):
        if path.name == 'base.html':
            continue
        for block in BLOCK.findall(path.read_text(encoding='utf-8')):
            for script in INLINE.findall(block):
                if DOM.search(script) and 'DOMContentLoaded' not in script:
                    offenders.append(str(path.relative_to(TEMPLATES)))
    assert not offenders, 'extra_scripts touches the DOM before it exists: ' + ', '.join(offenders)
