#!/bin/bash
set -e

# Resolve the desired runtime UID/GID from PUID/PGID (linuxserver.io convention).
# Defaults preserve the historical 1000:1000 behaviour, so existing deployments
# that don't set these variables are unaffected.
PUID="${PUID:-1000}"
PGID="${PGID:-1000}"

# Remap the 'may' group/user to the requested IDs when they differ from the
# baked-in ones. -o (non-unique) avoids failures when the target ID already
# exists in the base image (e.g. Unraid's 99:100 nobody:users, where GID 100
# is already taken by the Debian 'users' group).
current_gid="$(id -g may)"
if [ "$PGID" != "$current_gid" ]; then
    groupmod -o -g "$PGID" may
fi

current_uid="$(id -u may)"
if [ "$PUID" != "$current_uid" ]; then
    usermod -o -u "$PUID" may
fi

echo "[entrypoint] Running as may (PUID: $PUID, PGID: $PGID)"

# Ensure the data + uploads directories exist, then fix ownership for bind
# mounts. A recursive chown only runs where a folder's own ownership is wrong,
# so a correctly-owned (and possibly large) uploads directory doesn't slow
# startup on every restart. uploads is checked separately: in a data folder
# that already has the right owner, the mkdir above creates it as root (#56).
mkdir -p /app/data/uploads
if [ "$(stat -c '%u:%g' /app/data)" != "$PUID:$PGID" ]; then
    chown -R may:may /app/data
elif [ "$(stat -c '%u:%g' /app/data/uploads)" != "$PUID:$PGID" ]; then
    chown -R may:may /app/data/uploads
fi

# Run database migrations as the may user. Failures are logged rather than
# silently swallowed so upgrade problems are visible in container logs.
if ! gosu may flask db upgrade; then
    echo "[entrypoint] flask db upgrade failed — the app will attempt schema recovery on startup." >&2
fi

# Drop to 'may' user and run the application
exec gosu may "$@"
