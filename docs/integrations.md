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
Create vehicle sensors in Home Assistant:

```yaml
sensor:
  - platform: rest
    name: "OdoDash Vehicle Stats"
    resource: http://your-ododash-instance/api/ha/summary
    headers:
      Authorization: ******
    value_template: "{{ value_json.alerts_count }}"
    json_attributes:
      - total_vehicles
      - total_cost
```

Available endpoints: `/api/ha/status`, `/api/ha/vehicles`, `/api/ha/alerts`, `/api/ha/summary`

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
