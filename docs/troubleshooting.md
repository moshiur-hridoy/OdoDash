# Troubleshooting

[← Back to README](../README.md)

## Application Won't Start
- Check that all dependencies are installed: `pip install -r requirements.txt`
- Ensure the data directory is writable
- Check logs for specific error messages

## Database Issues
- Default SQLite database is created at `data/may.db`
- Ensure the directory exists and is writable
- For schema updates, the app handles migrations automatically

## Interface Not Translated
- The compiled catalogues (`app/translations/<lang>/LC_MESSAGES/messages.mo`)
  are build artefacts, not repository files. The app rebuilds any that are
  missing or older than their `.po` on startup
- If `app/translations` is read-only, the rebuild is skipped and a warning is
  logged; build them where the files are writable with
  `pybabel compile -d app/translations`

## Notification Issues
- **Email**: Verify SMTP settings and credentials in admin settings
- **ntfy**: Check your topic name is correct
- **Pushover**: Ensure admin has configured the app token
- **Webhook**: Verify the URL is accessible and accepts POST requests

## PDF Generation
- WeasyPrint requires system dependencies on some platforms
- On Ubuntu/Debian: `apt-get install libpango-1.0-0 libpangocairo-1.0-0`
- On macOS: `brew install pango`
