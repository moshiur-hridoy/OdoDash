"""docker-entrypoint.sh must leave the data and uploads folders writable (#56).

The block that fixes ownership is run on its own, with ``stat``, ``chown`` and
``mkdir`` replaced by shell functions, so no container or root is needed.
"""
import subprocess
from pathlib import Path

import pytest

ENTRYPOINT = Path(__file__).resolve().parent.parent / 'docker-entrypoint.sh'

APP_USER = '1000:1000'
ROOT = '0:0'


def _ownership_block():
    script = ENTRYPOINT.read_text()
    start = script.index('\nmkdir -p /app/data/uploads')
    end = script.index('# Run database migrations')
    return script[start:end]


def _chowns(data_owner, uploads_owner):
    stubs = f'''
set -e
PUID=1000
PGID=1000
mkdir() {{ :; }}
chown() {{ echo "chown $*"; }}
stat() {{
    case "${{@: -1}}" in
        /app/data) echo {data_owner} ;;
        /app/data/uploads) echo {uploads_owner} ;;
    esac
}}
'''
    result = subprocess.run(['bash', '-c', stubs + _ownership_block()],
                            capture_output=True, text=True, check=True)
    return result.stdout.splitlines()


def test_root_owned_uploads_in_a_correctly_owned_data_folder_is_fixed():
    assert _chowns(APP_USER, ROOT) == ['chown -R may:may /app/data/uploads']


@pytest.mark.parametrize('uploads_owner', [ROOT, APP_USER])
def test_a_wrongly_owned_data_folder_is_fixed_as_a_whole(uploads_owner):
    assert _chowns(ROOT, uploads_owner) == ['chown -R may:may /app/data']


def test_correct_ownership_is_left_alone():
    assert _chowns(APP_USER, APP_USER) == []
