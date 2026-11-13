"""The catalogue template lists every string the code marks for translation.

The Telegram bot shipped in 0.48.0 with 42 strings that never reached
messages.pot, so every language showed them in English while the
"every catalogue is complete" checks still passed: a string missing from the
template is missing from each .po too, so nothing looked untranslated. This
runs the same extraction the CLAUDE.md recipe does and compares msgids, so a
forgotten `pybabel extract` fails here instead of in production.
"""
import os
import subprocess
import sys

from babel.messages.pofile import read_po

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POT = os.path.join(ROOT, 'app', 'translations', 'messages.pot')


def _msgids(path):
    with open(path, 'rb') as f:
        catalog = read_po(f)
    return {m.id if isinstance(m.id, str) else m.id[0]
            for m in catalog if m.id}


def test_every_marked_string_is_in_the_template(tmp_path):
    fresh = tmp_path / 'messages.pot'
    subprocess.run(
        [sys.executable, '-m', 'babel.messages.frontend', 'extract',
         '-F', 'babel.cfg', '-k', '_l', '-o', str(fresh), '.'],
        cwd=ROOT, check=True, capture_output=True,
    )
    missing = sorted(_msgids(fresh) - _msgids(POT))
    assert missing == [], (
        f"{len(missing)} translatable strings are not in messages.pot. "
        "Run the pybabel extract/update steps in CLAUDE.md, then fill the "
        "catalogues:\n" + '\n'.join(repr(m) for m in missing[:20])
    )
