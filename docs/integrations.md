# Integrations

[← Back to README](../README.md)

## UK Fuel Prices

UK retailers publish their forecourt prices as open JSON feeds under the
government [fuel price transparency scheme](https://www.gov.uk/guidance/access-the-latest-fuel-prices-and-forecourt-data-via-api-or-email).
OdoDash can read those feeds and record the prices against your saved stations, so
price history and Cheapest Fuel stay current without manual entry. No API key is
needed.

To use it:

1. An admin enables it in **Settings → Integrations → UK Fuel Prices**.
2. Give each saved station its postcode — that is what stations are matched on
   the first time. Where a postcode covers more than one forecourt, coordinates
   (if set) and then brand break the tie.
3. Once a station has been matched, OdoDash remembers which forecourt it stands for
   and goes straight to it on later refreshes, so a station keeps reporting the
   same forecourt even if its postcode is edited. A remembered forecourt that
   drops out of the feed is reported as unmatched rather than quietly resolving
   to a different one.
4. Prices refresh in the background every six hours, and on demand with the
   **Update UK Prices** button on the Fuel Stations page or on a single
   station's price history.

Prices are stored one row per station, fuel type and day, so re-running the
refresh updates the day's entry rather than adding duplicates. Premium grades
are recorded separately (E5 as "Petrol Premium", SDV as "Diesel Premium").

The built-in retailer list follows the gov.uk guidance page. Retailers join and
leave the scheme, so the settings panel takes an optional override — one feed
per line, either `Retailer name|https://...` or a bare URL. A feed that is
unreachable is reported and the rest still apply.

## Home Assistant

The [ododash-homeassistant](https://github.com/moshiur-hridoy/ododash-homeassistant)
integration, installed through HACS, turns each vehicle into a Home Assistant
device with sensors and alerts, set up from the Home Assistant UI with no YAML.

[![Open your Home Assistant instance and open the OdoDash integration in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=moshiur-hridoy&repository=ododash-homeassistant&category=integration)

Settings → Integrations → Home Assistant walks through three steps:

1. **Create key.** Create a Home Assistant key (it starts with `odoha_`). It
   works only on `/api/ha/*`: it can read your vehicles and log fuel, and
   `/api/v1` and the calendar feed refuse it. Regenerate or revoke it from the
   same panel; Home Assistant then asks for the new key.
2. **Install.** "Add to Home Assistant" opens your Home Assistant at the HACS
   page for the integration. Download it and restart Home Assistant. HACS is
   required; see [hacs.xyz](https://hacs.xyz).
3. **Connect.** Add the OdoDash integration in Home Assistant and paste the
   server address and key shown in this step. Behind a reverse proxy, use the
   address Home Assistant can reach rather than the one OdoDash shows.

The account's main API key (`odo_`) still works on `/api/ha/*`, so existing
YAML setups keep working, but it can do everything the API can. Prefer the
Home Assistant key.

### REST API

Every `/api/ha/*` endpoint takes an `Authorization: Bearer <key>` header and
covers the vehicles you can see in OdoDash: your own, ones shared with you and
instance-shared ones.

| Endpoint | Returns |
|---|---|
| `GET /api/ha/status` | `status`, `user`, `version` |
| `GET /api/ha/overview` | everything below in one request (used by the integration) |
| `GET /api/ha/vehicles`, `/api/ha/vehicles/<id>` | vehicle details |
| `GET /api/ha/vehicles/<id>/stats[?days=N]` | totals, average consumption, last fill |
| `GET /api/ha/alerts` | due maintenance, recurring expenses, expiring documents, reminders |
| `GET /api/ha/summary` | account-wide totals and alert count |
| `POST /api/ha/fuel/add` | logs a fill-up |

`/api/ha/overview` returns `version`, `user`, `currency`, `alerts_count` and a
`vehicles` list. Each vehicle carries its details, `is_electric`,
`current_odometer`, `distance_unit`, `volume_unit`, `currency_symbol`,
`avg_consumption` and `consumption_unit` (both `null` for a vehicle metered in
engine hours), `total_cost`, `total_fuel_cost`, `total_expenses`,
`cost_last_30_days`, `last_fill_date`, `last_fill_volume`, `last_fill_cost`,
`last_charge` (`date`, `kwh_added`, `start_soc`, `end_soc`, `total_cost` for an
electric vehicle with a charging session, otherwise `null`) and its own
`alerts`.

### YAML sensors

Without the integration you can still create sensors with the REST platform
(Settings → Integrations → Home Assistant → Advanced: YAML sensors):

```yaml
sensor:
  - platform: rest
    name: "OdoDash Vehicle Stats"
    resource: http://your-ododash-instance/api/ha/summary
    headers:
      Authorization: Bearer YOUR_HOME_ASSISTANT_KEY
    value_template: "{{ value_json.alerts_count }}"
    json_attributes:
      - total_vehicles
      - total_cost
```

## Calendar Subscription
Subscribe to reminders in your calendar app:

1. Go to Settings > Integrations > Calendar
2. Copy the webcal URL (for Apple Calendar, Outlook) or HTTPS URL (for Google Calendar)
3. Add as a subscribed calendar in your app

The calendar includes:
- Maintenance schedules
- Recurring expense due dates
- Document expiry dates
- Custom reminders
