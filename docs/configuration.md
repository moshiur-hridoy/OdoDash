# Configuration

[← Back to README](../README.md)

Copy `.env.example` to `.env` and configure:

```bash
# Secret key for session encryption (optional)
SECRET_KEY=your-secure-random-string

# Database location (optional, defaults to SQLite in the app's data folder)
# Note the slashes: sqlite:///path is relative, sqlite:////path is absolute.
DATABASE_URL=sqlite:////srv/may/data/may.db
# PostgreSQL is also supported:
# DATABASE_URL=******host:5432/may

# Upload folder for attachments (optional)
UPLOAD_FOLDER=/srv/may/data/uploads
```

If you don't set `SECRET_KEY`, OdoDash generates one on first start and saves it to
`.secret_key` in its data folder, so logins survive restarts. Set it yourself if
you'd rather manage the key, or if you run more than one instance behind a load
balancer and want them to share sessions.

The supplied `docker-compose.yml` passes a placeholder `SECRET_KEY` when you
haven't set one of your own, so under Compose OdoDash signs sessions with that
rather than generating a key. Set `SECRET_KEY` in `.env` next to
`docker-compose.yml`, or remove the line from the compose file to let OdoDash
generate and keep its own.

The `.env` file must sit next to `config.py` in the application directory, and
it is read when OdoDash starts. Variables set in the real environment take
precedence over `.env`.

Under Docker Compose, `.env` is only used for `${VAR}` substitution in
`docker-compose.yml` (for example `SECRET_KEY`). `DATABASE_URL` and
`UPLOAD_FOLDER` are set in the compose `environment:` block, so changing them
in `.env` has no effect — edit `docker-compose.yml` instead.

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Session encryption key | Generated on first start and saved to `data/.secret_key` |
| `DATABASE_URL` | Database connection string (SQLite or PostgreSQL) | SQLite at `data/may.db` inside the application directory (`/app/data/may.db` in Docker) |
| `UPLOAD_FOLDER` | Path for file uploads | `data/uploads` inside the application directory (`/app/data/uploads` in Docker) |
| `PUID` | User ID the container runs as (linuxserver.io convention) | `1000` |
| `PGID` | Group ID the container runs as (linuxserver.io convention) | `1000` |
| `TAILWIND_ASSET_URL` | Local Tailwind Play CDN JS path | `/static/vendor/tailwindcss.js` |
| `TAILWIND_CDN_URL` | Tailwind CDN fallback URL | `https://cdn.tailwindcss.com` |
| `HTMX_CDN_URL` | HTMX CDN URL | `https://unpkg.com/htmx.org@1.9.10` |

By default, Tailwind loads from `app/static/vendor/tailwindcss.js` and falls back to the CDN URL if the local asset is missing.
