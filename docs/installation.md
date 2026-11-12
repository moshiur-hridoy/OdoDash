# Installation

[← Back to README](../README.md)

## Quick Start with Docker

```bash
# Clone your OdoDash fork
git clone https://github.com/moshiur-hridoy/OdoDash.git
cd OdoDash

# Run via Docker Compose
docker compose up -d
```

Or download the compose file directly:

```bash
# Create a directory for OdoDash
mkdir ododash && cd ododash

# Download docker-compose.yml
curl -O https://raw.githubusercontent.com/moshiur-hridoy/OdoDash/main/docker-compose.yml

# Start the container
docker compose up -d
```

Or run directly with Docker:

```bash
docker run -d \
  --name ododash \
  -p 5050:5050 \
  -v ododash_data:/app/data \
  -e SECRET_KEY=your-secret-key \
  -e PUID=1000 \
  -e PGID=1000 \
  ghcr.io/moshiur-hridoy/ododash:latest
```

> **Running as a specific user (PUID/PGID):** OdoDash follows the [linuxserver.io](https://docs.linuxserver.io/general/understanding-puid-and-pgid/) convention. Set the optional `PUID` and `PGID` environment variables to make the container run as a specific host user/group so bind-mounted data is owned correctly. They default to `1000:1000`. On Unraid, set `PUID=99` and `PGID=100`.

Access the application at `http://localhost:5050`

**First-time login:**
- Username: `admin`
- Password: Check your container logs for the auto-generated password

On first run, if no `ADMIN_PASSWORD` environment variable is set, OdoDash generates a secure random password and prints it to the console:

```
============================================================
SECURITY NOTICE: Default admin account created
Username: admin
Password: <randomly-generated-password>
Please change this password immediately after first login!
Set ADMIN_PASSWORD environment variable to avoid this message.
============================================================
```

To view the password, run:
```bash
docker logs ododash
```

💡 **Tip:** Set `ADMIN_PASSWORD` in your docker-compose.yml or environment to use a fixed password.

## Portainer

There are two ways to deploy OdoDash as a Portainer stack. The first is the simplest.

### Option 1: Paste the compose file (Web editor)

Uses the published image, so nothing is built on your server.

1. In Portainer go to **Stacks → Add stack**, name it `ododash` and choose **Web editor**.
2. Paste this:

```yaml
services:
  ododash:
    image: ghcr.io/moshiur-hridoy/ododash:latest
    container_name: ododash
    restart: unless-stopped
    ports:
      - "${ODODASH_PORT:-5050}:5050"
    volumes:
      - ododash_data:/app/data
    environment:
      SECRET_KEY: "${ODODASH_SECRET_KEY:?Set ODODASH_SECRET_KEY}"
      ADMIN_PASSWORD: "${ODODASH_ADMIN_PASSWORD:?Set ODODASH_ADMIN_PASSWORD}"
      DATABASE_URL: "sqlite:////app/data/may.db"
      UPLOAD_FOLDER: "/app/data/uploads"
      PUID: "${PUID:-1000}"
      PGID: "${PGID:-1000}"

volumes:
  ododash_data:
```

3. Under **Environment variables** add:

| Variable | Value |
| --- | --- |
| `ODODASH_SECRET_KEY` | A long random string, for example the output of `openssl rand -hex 32` |
| `ODODASH_ADMIN_PASSWORD` | The password you want for the `admin` user |
| `ODODASH_PORT` | Optional. Host port, defaults to `5050` |

4. Click **Deploy the stack** and open `http://<your-server>:5050`.

Your data lives in the `ododash_data` volume, so redeploying or pulling a newer image keeps it. To update, open the stack and use **Pull and redeploy**.

> To keep data in a host folder instead, replace the volume line with `- /opt/ododash/data:/app/data` and set `PUID`/`PGID` to the folder's owner.

### Option 2: Build from the repository

Use this if you want Portainer to build the image from the source (for example to run your own changes).

1. **Stacks → Add stack → Repository**.
2. Repository URL: `https://github.com/moshiur-hridoy/OdoDash`, reference `refs/heads/ododash-release`.
3. Compose path: `docker-compose.portainer.yml`.
4. Add the environment variables `ODODASH_SECRET_KEY` and `ODODASH_ADMIN_PASSWORD`. `ODODASH_DATA_PATH` (default `/opt/ododash/data`) and `ODODASH_PORT` are optional.

This variant builds the image on every redeploy, so it takes longer than Option 1.

## Manual Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Compile the translation catalogues (the .mo files are build artefacts and
# are not in the repository; the app also rebuilds stale ones on startup)
pybabel compile -d app/translations

# Run the application
python run.py
```
