# Public demo

[← Back to README](../README.md)

Demo mode turns an OdoDash instance into a shared showcase that anyone can open without installing anything.

## What visitors see

- A year of sample vehicles, fuel logs, expenses, trips and reminders.
- A login page that shows the credentials: username `demo`, password `demo` (already filled in).
- Full freedom to add, edit and delete vehicle data.
- Refused with "This is disabled in the public demo": changing the password or email, managing users, branding, restoring backups, API keys and every outbound integration (SMTP, webhooks, DVLA, Tessie, fuel-price feeds). This stops one visitor locking out the next.
- Uploads are capped at 5 MB.

The `demo` / `demo` login is fixed. `ADMIN_USERNAME` and `ADMIN_PASSWORD` are ignored while `DEMO_MODE` is on.

## Hosting it on your own server (recommended)

A free Render instance sleeps when idle and takes over a minute to wake, which is a poor first impression. A server that is always on answers instantly.

[docker-compose.demo.yml](../docker-compose.demo.yml) is a ready stack for Portainer:

1. **Stacks → Add stack**, name it `ododash-demo`.
2. Choose **Web editor** and paste the contents of `docker-compose.demo.yml` (or choose **Repository** with compose path `docker-compose.demo.yml`).
3. Add the environment variable `ODODASH_DEMO_SECRET_KEY` (any long random string, for example `openssl rand -hex 32`). Optional: `ODODASH_DEMO_PORT` (default `5052`) and `DEMO_RESET_EVERY` (seconds, default `86400`).
4. **Deploy the stack.** The demo is on `http://<your-server>:5052`.
5. Point your reverse proxy at that port, for example in Caddy: `demo.example.com { reverse_proxy ododash-demo:5050 }` (the proxy must share a Docker network with the stack) or `reverse_proxy localhost:5052`.

How it stays clean: the data folder is a `tmpfs` (memory), so there is no volume. Each restart of the demo container begins with an empty database, so the sample data and the `demo` / `demo` login are created again. A second tiny container restarts the demo every `DEMO_RESET_EVERY` seconds (nightly by default), so visitors' edits do not pile up. To reset right now, restart the `ododash-demo` container in Portainer.

Notes:
- The reset container mounts the Docker socket. Keep this stack to the demo only and do not publish a port for it.
- The demo container is limited to 512 MB of memory and one CPU, because the instance is public. Uploads count against that memory, and are capped at 5 MB each.
- Always serve it over HTTPS and on its own subdomain.

## Hosting it on Render

Use this if you have no server of your own.

1. **New → Web Service → Deploy an existing image**, image URL `ghcr.io/moshiur-hridoy/ododash:latest`.
2. Choose the Free instance type, and **do not attach a disk**. The demo is meant to come back clean after Render restarts or wakes it.
3. Environment variables:

| Variable | Value |
| --- | --- |
| `DEMO_MODE` | `1` |
| `SECRET_KEY` | A long random string |
| `PORT` | `5050` (the image listens on 5050) |

4. Set the health check path to `/health`.
5. Deploy and open the service URL. The login page should show the "Live demo" box.

To pick up a new release, use **Manual Deploy → Deploy latest reference** (or **Clear build cache & deploy**) so Render pulls the newest `latest` image.

## Troubleshooting: the demo login is rejected

The demo account is created only when the database is **empty**. If any user already exists, seeding is skipped and `demo` / `demo` will not work. Check these in order:

1. **No "Live demo" box on the login page.** The instance is not running in demo mode. Confirm `DEMO_MODE=1` is set and that the image is **v0.47.0 or newer** (demo mode first shipped in 0.47.0). Redeploy after changing it.
2. **The box shows, but the login fails.** The database already holds users, usually because a disk is attached or the instance ran before `DEMO_MODE` was set. Remove the disk (or its contents) and redeploy, so the next start seeds an empty database.
3. **Still failing.** Open the service **Logs** and look for errors around startup, such as `Could not stamp alembic head` or a database error. A free instance that is waking up can also take about a minute to respond; wait and retry.
