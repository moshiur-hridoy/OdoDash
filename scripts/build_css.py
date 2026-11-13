#!/usr/bin/env python
"""Compile the Tailwind stylesheet.

Usage:
  python scripts/build_css.py            # one minified build
  python scripts/build_css.py --watch    # rebuild on every template change

Reads app/static/css/src/app.css and tailwind.config.js and writes
app/static/css/app.css. That output is a build artefact (ignored by git, like
the compiled translation catalogues): the Dockerfile builds it for the image,
and a checkout without it still renders, because base.html falls back to the
in-browser Tailwind runtime.

The standalone Tailwind CLI needs no Node. It is downloaded once per platform
into .cache/tailwindcss/, pinned to one version, and refused unless its
SHA-256 matches the checksum Tailwind published for that release.
"""
import argparse
import hashlib
import os
import platform
import stat
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

VERSION = 'v3.4.17'

# From https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.17/sha256sums.txt
CHECKSUMS = {
    'linux-arm64': '69b1378b8133192d7d2feb12a116fa12d035594f58db3eff215879e4ad8cf39b',
    'linux-armv7': '704e7d91afba6e1f630889afd0d7db36b4634e628512cc141d504a5beae28860',
    'linux-x64': '7d24f7fa191d2193b78cd5f5a42a6093e14409521908529f42d80b11fde1f1d4',
    'macos-arm64': 'a1d0c7985759accca0bf12e51ac1dcbf0f6cf2fffb62e6e0f62d091c477a10a3',
    'macos-x64': '6cbdad74be776c087ffa5e9a057512c54898f9fe8828d3362212dfe32fc933a3',
    'windows-arm64.exe': '76f516476784c00f1562160b5758e3d8f0e6c48957efb26b5b50fbdfd76aa382',
    'windows-x64.exe': '67f1c5e3f5a03406a7bf5badf5ada09b79f3ae78ec43450c15f7e983068da346',
}

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'app' / 'static' / 'css' / 'src' / 'app.css'
OUTPUT = ROOT / 'app' / 'static' / 'css' / 'app.css'
CONFIG = ROOT / 'tailwind.config.js'
CACHE = ROOT / '.cache' / 'tailwindcss'


def platform_key():
    system = sys.platform
    machine = platform.machine().lower()
    if machine in ('x86_64', 'amd64'):
        arch = 'x64'
    elif machine in ('arm64', 'aarch64'):
        arch = 'arm64'
    elif machine.startswith('armv7'):
        arch = 'armv7'
    else:
        sys.exit(f'No Tailwind {VERSION} binary for CPU architecture {machine!r}.')
    if system.startswith('linux'):
        key = f'linux-{arch}'
    elif system == 'darwin':
        key = f'macos-{arch}'
    elif system in ('win32', 'cygwin'):
        key = f'windows-{arch}.exe'
    else:
        sys.exit(f'No Tailwind {VERSION} binary for platform {system!r}.')
    if key not in CHECKSUMS:
        sys.exit(f'No Tailwind {VERSION} binary for {key}.')
    return key


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_binary():
    key = platform_key()
    expected = CHECKSUMS[key]
    binary = CACHE / VERSION / f'tailwindcss-{key}'
    if binary.exists() and sha256(binary) == expected:
        return binary

    url = f'https://github.com/tailwindlabs/tailwindcss/releases/download/{VERSION}/tailwindcss-{key}'
    print(f'Downloading Tailwind {VERSION} ({key})...', file=sys.stderr)
    binary.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=binary.parent, prefix='.download-')
    try:
        with os.fdopen(fd, 'wb') as out, urllib.request.urlopen(url, timeout=120) as resp:
            while chunk := resp.read(1 << 20):
                out.write(chunk)
        actual = sha256(tmp)
        if actual != expected:
            sys.exit(
                f'Checksum mismatch for {url}\n  expected {expected}\n  got      {actual}\n'
                'Refusing to run it.'
            )
        os.chmod(tmp, os.stat(tmp).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        os.replace(tmp, binary)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return binary


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--watch', action='store_true', help='rebuild whenever a source file changes')
    args = parser.parse_args()

    binary = ensure_binary()
    cmd = [str(binary), '--config', str(CONFIG), '--input', str(SOURCE), '--output', str(OUTPUT)]
    cmd.append('--watch' if args.watch else '--minify')
    # Run from the repository root so the content globs in the config resolve.
    # The CLI bundles its own browser data; the "caniuse-lite is outdated"
    # notice it prints is about that bundle and is not actionable here.
    env = dict(os.environ, BROWSERSLIST_IGNORE_OLD_DATA='1')
    result = subprocess.run(cmd, cwd=ROOT, env=env)
    if result.returncode == 0 and not args.watch:
        print(f'Wrote {OUTPUT.relative_to(ROOT)} ({OUTPUT.stat().st_size // 1024} KB)', file=sys.stderr)
    return result.returncode


if __name__ == '__main__':
    sys.exit(main())
