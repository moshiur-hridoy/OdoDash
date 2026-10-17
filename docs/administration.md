# Administration, Roles and API

[← Back to README](../README.md)

## Admin Settings

Administrators can configure:
- **SMTP Settings**: Email server for notifications
- **Pushover**: Application token for push notifications
- **DVLA API**: API key for UK vehicle lookups ([get one here](https://developer-portal.driver-vehicle-licensing.api.gov.uk/))
- **UK Fuel Prices**: live forecourt prices for saved stations (see below)
- **Branding**: Custom logo, app name, tagline, and primary color
- **User Management**: Create, edit, and manage user accounts, including each account's role

## User Roles

Every account has a role, set by an administrator when the account is created
or from Settings → Users → Edit:

| Role | What the account can do |
| --- | --- |
| **Editor** | Full control of the vehicles and data the account can see. This is the default, and matches how OdoDash behaved before roles existed. |
| **Contributor** | Record fuel fill-ups and charging sessions. Everything else — expenses, maintenance, trips, reminders, vehicles — is read-only. Suited to drivers. |
| **Viewer** | See everything the account has access to, but change nothing. Suited to a vehicle owner who only wants the figures. |

Administrators always have full access whatever role is stored against them.
Roles decide what an account may *change*; what it can *see* is still governed
by vehicle ownership and sharing, so a driver only sees the vehicles shared
with them.

Roles apply everywhere, not just in the browser: the REST API and the Home
Assistant endpoints refuse writes the account's role does not cover, returning
`403` with a `permission_denied` code. Every account can still manage its own
settings, password, notifications and API key.

## API

OdoDash includes a REST API for automation and integrations:

```bash
# Generate an API key in Settings > API
curl -H "Authorization: ******" \
  http://localhost:5050/api/v1/vehicles
```

Vehicles, fuel logs, expenses, trips, and charging sessions can all be read and
created through the API. See the API documentation at `/api/docs` when logged in.
