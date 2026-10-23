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
