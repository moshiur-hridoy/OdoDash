# Usage Guide

[← Back to README](../README.md)

## Dashboard
The main dashboard shows an overview of all your vehicles with key statistics:
- Total fuel costs and consumption averages
- Recent fuel logs and expenses
- Upcoming reminders and overdue alerts
- Vehicle photo cards showing make/model/year and fuel type at a glance

## Vehicles
Add and manage your vehicles with detailed information:
- Make, model, year, and registration
- Fuel type and tank capacity
- Custom specifications and notes
- **Tracking Unit**: Choose whether a vehicle's odometer counts distance or engine hours — plant and machinery are metered in hours, and their consumption and running costs are worked out per hour rather than per mile. The unit is fixed once anything has been logged against the odometer, since changing it would reinterpret every existing reading. Readings and the figures beside them are labelled in hours throughout ("h", "L / h", "Cost per h"), every form that records a reading calls the field "Engine hours" rather than "Odometer" — including the trip and charging forms — and a maintenance schedule for such a vehicle is set in engine hours instead of kilometres or miles. The CSV exports state each row's own unit, so engine hours are never filed under a distance heading alongside the cars, and the Home Assistant endpoints report the unit the reading is actually in — `unit_distance` (and `distance_unit` on the stats endpoint) is `h` for such a vehicle rather than the account's distance preference. Where a total spans both kinds of vehicle, as the dashboard and the trip summaries can, it says "mixed units" rather than adding engine hours to miles and calling the result a distance. The tracking unit is set on the vehicle page and is still neither exposed nor settable over the REST API; vehicles created there are tracked by distance
- **Photo Gallery**: Upload as many photos per vehicle as you like from the "Photos" section on the vehicle page. Any of them can be set as the main photo — the one shown on the dashboard and vehicle list — and the vehicle page steps through the rest with left/right arrows
- **Vehicle Sharing**: Mark a vehicle as "Shared" to make it visible and loggable by all users on the instance
- **Upcoming Maintenance**: Vehicle detail pages show a live panel of scheduled maintenance tasks, with overdue and due-soon alerts
- **Parts & Consumables**: Collapsible section on the vehicle page remembers your expand/collapse preference per vehicle
- **PDF Report**: The "PDF" button downloads a summary of the vehicle, its specifications, its parts and consumables, its fuel logs and its expenses. "PDF + Receipts" does the same and appends the receipt images attached to those entries, which is the version to hand to an accountant or employer. Non-image attachments (PDF scans, for example) are listed at the end of the report rather than embedded.
- **Service Timeline**: Combined history of fuel, expenses, and charging, including any notes recorded against an entry and links to its attachments
- **Expenses by Category**: A collapsible bar chart on the vehicle page breaking that vehicle's expenses down by category, alongside the dashboard chart covering the whole fleet. Vehicles with no expenses recorded do not show it.

## Fuel Logs
Track every fill-up with:
- Date, odometer reading, and fuel amount
- Total cost and price per unit
- Full tank indicator for accurate consumption calculations
- Automatic MPG/L per 100km calculations
- Fuel type selection for vehicles that take more than one fuel, including hybrids (petrol or diesel), so station price charts stay grouped by the fuel actually bought
- Each fuel is measured on its own: consumption figures, averages and the consumption trend chart count only the logs of that fuel type, so an AdBlue refill on a diesel never lands in the diesel L/100km. Logs recorded before the fuel type selector existed count as the vehicle's own fuel type.
- "AdBlue/DEF" is available as a vehicle's secondary fuel type, for the fluid a diesel tracks alongside its fuel. It is an exhaust additive rather than a fuel, so it is not offered as a vehicle's own fuel type and counts as no tailpipe CO2.
- The fuel log list shows the fuel type of each entry
- Optional sales tax paid on the fill-up (VAT, GST/HST/PST, or whatever applies where you are), entered as the amount shown on the receipt and treated as part of the total cost rather than added to it. Where more than one tax applies, enter the sum. The fuel log list totals it by calendar year, each fill-up's tax is shown under its cost, and the figures appear in the vehicle PDF report, the CSV and JSON exports and the API. Quick entry mode does not ask for it, so a fill-up logged that way records no tax and the yearly total will be short by that amount; edit the log afterwards to add it.

Saving a fuel log returns you to the fuel log list, unless you started from a vehicle page, in which case you go back to that vehicle. Deleting one does the same: from the fuel log list you stay on the list, from a vehicle page you return to that vehicle. Notes behave the same way.

#### Dual-fuel vehicles (petrol + LPG)
Give the vehicle a secondary fuel type and each fill-up gets a **Fuel Type**
selector. OdoDash then keeps the two fuels apart: each fuel gets its own average on the
vehicle page, built only from fill-ups of that fuel, because a combined
figure would describe neither.

The odometer cannot say which kilometres were run on LPG and which on petrol,
so a fill-up of a dual-fuel vehicle also asks for **Distance on this fuel** —
how far was driven on the fuel being logged. It is only asked for where it is
genuinely ambiguous: a stretch in which you filled with one fuel only is worked
out from the odometer as usual, so a car converted to LPG keeps its earlier
petrol figures. Where the two fuels are mixed and that distance is missing, the
page says the figure cannot be worked out without it rather than showing one
derived from the wrong distance.

The distance is entered in the vehicle's own unit, the one its odometer reads
in. Both the fuel type and the distance attributed to it appear in the CSV and
JSON exports, in backups and over the REST API, where they can be set on a
fill-up as well as read. The `average_consumption` figure in the API's vehicle
stats covers the vehicle's primary fuel; the per-fuel figures are on the vehicle
page. A diesel tracking AdBlue is not a dual-fuel vehicle for this purpose —
AdBlue propels nothing — so it is never asked for the distance.

## EV Charging
Log charging sessions for electric and plug-in hybrid vehicles:
- Date, optional start and end times, and the odometer reading
- Energy added in kWh, state of charge at each end, and cost — the total is worked out from the price per kWh where you do not enter it yourself
- Charger type, location and network, so home and public charging can be told apart
- The list is ordered by date, most recent first; sessions sharing a date are ordered by their odometer reading, so the most recent charge sits at the top. This matters most on a plug-in hybrid, which may be charged several times in a day

## Expenses
Categorize all vehicle-related costs:
- Maintenance & Repairs
- Inspection (MOT, roadworthy checks)
- Insurance
- Tax & Registration
- Parking & Tolls
- Accessories
- Other expenses

Record odometer readings alongside costs, and expand any expense row to see vendor, notes, and links to any attached receipts inline. An expense can have several receipts — select more than one file when adding or editing it. An odometer recorded against an expense counts towards the vehicle's latest reading, alongside fuel logs, trips and charging sessions. Saving an expense returns you to the expenses list, unless you started from a vehicle page, in which case you go back to that vehicle.

## Trips
Log journeys for mileage and tax records:
- Date, purpose, start and end locations, and the odometer at each end
- Optional fuel gauge readings at the start and end of the trip, entered as a percentage of a full tank
- Where the vehicle has a tank capacity set, the fuel used on the trip is worked out from those readings and shown on the trip list, giving a per-trip view of consumption between fill-ups
- Reusable templates for journeys you make often, and a business/personal summary report per year
- The list is ordered by date, most recent first; trips sharing a date are ordered by their odometer reading, so the journey you drove last sits at the top

## Reminders
Never miss important dates:
- MOT/Inspection due dates
- Service intervals
- Insurance renewals
- Tax payments
- Custom reminders with flexible recurrence
- **Log expense**: record what an outstanding reminder cost. The expense form opens pre-filled with the vehicle, the reminder's title and a matching category; saving it records the expense, ticks the reminder off and schedules its next occurrence. The cost is typed at that point, so reminders for fees that change — registration, for instance — stay accurate.

## Maintenance Schedules
Plan regular maintenance tasks:
- Set intervals by mileage or time (e.g., oil change every 10,000 km or 12 months)
- A vehicle tracked in engine hours takes its interval in hours instead (e.g., every 250 hours). The km and miles boxes are hidden for it, since no distance interval could be compared against an hour reading, and "due soon" means within 25 hours rather than 500
- Track completion history
- Automatic reminder generation
- Link to expenses when completed

## Tire Sets
Track summer, winter and all-season sets separately:
- Record a set with its type, size, purchase date, purchase odometer and cost
- Put a set on or take it off with a date and odometer reading; fitting a set
  automatically takes the set currently on the vehicle off at the same reading
- The distance covered on each set is the sum of every period it spent fitted,
  measured against the vehicle's latest odometer reading while it is still on
- Retire a set when it is worn out or sold; the history stays

## Recurring Expenses
Track regular payments:
- Insurance premiums
- Road tax
- Subscriptions and memberships
- Custom recurrence patterns (monthly, quarterly, yearly)
- An optional vendor / service provider, carried on to every expense the
  schedule creates
- Automatic calendar integration

## Documents
Store important vehicle documents:
- Insurance certificates
- Registration documents
- Service manuals and instruction booklets (up to 300MB)
- MOT certificates
- Any file type (PDF, images, Word, Excel, text, ePub) with expiry date tracking

## Fuel Stations
Save your favorite stations:
- Quick selection during fuel logging
- Track prices at different stations
- Notes and location information
- UK stations can pull live prices from the government fuel price feeds
  (see [UK Fuel Prices](#uk-fuel-prices))

## Notifications
Configure your preferred notification method:
- **Email**: SMTP server configuration (admin)
- **ntfy**: Free push notifications via ntfy.sh or self-hosted
- **Pushover**: iOS/Android push notifications
- **Webhook**: HTTP POST for Home Assistant, Discord, Slack, etc.

## Import & Restore
**Settings → Integrations → Import Data** holds the import options, including
**Restore May Backup** for moving data from another May or OdoDash instance:

- It takes either file the export page produces — the JSON export (`.json`) or
  the full backup (`.zip`). A full backup also brings across documents,
  attachments and vehicle images; a JSON export carries the records only.
- The restore merges into the account you are signed in as. Nothing is deleted
  or overwritten, and records already present are skipped rather than
  duplicated, so running the same backup twice is harmless.
- A preview of exactly what will be added is shown before anything is written,
  and nothing is saved until you confirm it.

Imports from Hammond and Fuelly live in the same place.

## Good to know

From v0.44.0, leave the fuel odometer field blank when the reading was not
recorded. Older zero readings are retained but excluded from consumption until
confirmed: edit the entry and enter `0` if it really was zero. Positive readings
remain usable. An unknown reading inside a fill-to-fill interval makes that
interval unsuitable for consumption calculations; other complete intervals
still contribute. CSV exports leave unknown readings blank, and backups retain
whether a reading was confirmed.

Open **Maintenance History** from the maintenance list or a vehicle to see
recorded services and existing maintenance expenses. Completing a schedule
records a service even without an expense. Editing or deleting the schedule
keeps its history. Upgrades retain the last known service details, but cannot
recover values overwritten before this version.

When fitting tires, select **Front axle**, **Rear axle**, or **All axles**.
Front and rear pairs can stay fitted simultaneously. Replacing one axle of an
all-axle set keeps the unaffected pair fitted and continues its distance history.

UK fuel lookups still use the configured retailer feeds. Failed feeds now have
clearer diagnostics; they do not erase saved prices. Government Fuel Finder API
support is still pending verification of its authenticated API contract.
