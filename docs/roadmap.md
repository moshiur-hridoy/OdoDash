# OdoDash Roadmap: fixes, then design

Working order after 0.47.0, written 2026-11-12. Work **one item at a time**:
fix, add a regression test, run the relevant tests, commit to `dev`, tick the
box here, then start the next one. Issue-level detail and the completion record
stay in [upstream-issues-fix-plan.md](upstream-issues-fix-plan.md).

Each block below ends in a release, so fixes reach users without waiting for
the whole list.

## Block A: data correctness (target 0.47.1)

- [x] **#403 Recurring expenses duplicate.** Root cause: Gunicorn runs two
      workers and each starts its own hourly scheduler thread, so both
      generate the same due period. Fix at two levels: only one process runs
      the scheduler (file lock), and each period is claimed with a conditional
      update so a second process or container can never generate it again.
      The same lock stops reminder emails being sent twice.
- [ ] **#384 Total distance differs from the odometer.** Agree the rule first
      (latest reading minus purchase/first reading, across fuel, trips,
      charging, expenses). Upstream PR #409 (starting odometer) is a candidate
      to adapt.
- [ ] **#412 EV overview missing data.** Check after #384, since it likely
      shares the distance calculation.

## Block B: verification debts (target 0.47.1)

- [ ] **#410 PostgreSQL upgrade.** Run the upgrade on a real PostgreSQL
      container and record the result.
- [ ] **#381 Large numbers.** Check PDFs, mobile and two non-English locales.
- [ ] **#418 Consumption spikes.** Blocked on the reporter's data; ask on the
      upstream issue before doing anything.

## Block B2: UX quick wins (target 0.47.1)

From the UX review on 2026-11-12. Small fixes that users notice every day.

- [x] **Dark mode rows and toggles.** An old pass that paired light and dark
      backgrounds also matched `hover:bg-gray-50` and `after:bg-white`, so
      dark-mode rows stayed highlighted and four settings toggles vanished
      into the card. `tests/test_dark_mode_classes.py` guards it.
- [x] **Number grouping.** Distances and odometer readings now follow the
      thousand-separator preference (`groupnum`), so they match the money
      amounts and the last odometer.
- [x] **Fuel form keeps typed values.** A refused add or edit re-renders the
      form (422) with the message under the failing field, not a blank form.
- [ ] The same for the charging form (two error redirects), then check the
      remaining forms for the pattern.
- [ ] `validate_positive_number` (`app/security.py`) builds English-only
      messages, which now show inline on the fuel form. Make them
      translatable.
- [ ] The same old pass left about 48 conflicting `dark:text-*` pairs, mostly
      in `auth/settings.html`. They are subtle shade differences only.

## Block C: mobile design pass (target 0.48.0)

The dashboard, navigation and quick fuel entry are done. Every list page is
still a wide table on phones (fuel, expenses, tires, notes, allowance, users).

- [ ] Shared mobile card-list pattern for table pages, starting with
      **fuel log** and **expenses** (the most used), then tires, notes,
      allowance and users.
- [ ] Forms on phones: one column, larger touch targets, sticky Save bar.
- [ ] Vehicle page (`vehicles/view.html`, ~1,500 lines): tabbed sections on
      phones instead of one long scroll.
- [ ] Settings (`auth/settings.html`, ~2,300 lines): split into tabs or
      sections with a side/top index.
- [ ] Empty states with a clear first action on every list page.
- [ ] Fuel and expenses: vehicle, date-range and category filters with a
      "this month" summary row (the fuel list is already paginated). Build
      them into the card-list pattern rather than the old tables.
- [ ] Deleting: replace the 25 native `confirm()` dialogs with an Undo
      toast, or a styled confirm where undo is not possible.
- [ ] After saving a fill-up, say what it worked out to (consumption and
      how it compares with the vehicle's average) instead of only "added".
- [ ] Dashboard: a this-month / this-year / all-time switch, compact cards
      when Reminders or Cheapest Fuel have nothing to show, and a first-run
      checklist (vehicle, first fill-up, first reminder).
- [ ] Vehicle page: one primary action with the rest under "More", and
      photos moved below the stats with a drop zone instead of the raw file
      input.
- [ ] Accessibility audit: only 18 `aria-label`s exist; check the icon-only
      buttons (sidebar footer, row actions) first.

## Block D: small feature requests (target 0.48.x)

- [ ] **#420** Charging: derive price per kWh from total cost and energy.
- [ ] **#416** Fuel: separate loyalty-card discount on the total.
- [ ] **#385 / #406** Expense categories (Car Payment, MOT/Service). Upstream
      PR #407 is a candidate to adapt.

After Block D, return to the feature plan (receipt scan, insights). Bangla
translation is low priority: most vehicle owners in Bangladesh already use
English-language apps, so Bangla waits until someone asks for it.

## Block E: gaps found against similar projects (target 0.5x)

From a comparison on 2026-11-23 with Tracktor, LubeLogger, Hammond, MyGarage,
MASHINA and MotoMate, extended on 2026-11-25 from the READMEs, docs and public
screenshots of LubeLogger and Tracktor (read, not installed or tried). Only gaps are listed; OdoDash already leads on
import/restore (May, CSV, Hammond, Clarkson, Fuelly), REST API,
Home Assistant, calendar feed, DVLA and UK fuel prices. Ordered by value for
the effort. Agree the scope of each item before building it.

Targets set 2026-11-25 (milestones on GitHub): **0.53.0** is the small items and the ones the
maintainer needs; **0.54.0** follows; items with no target are open for contributors
(`help wanted`) or need a design first.

- [ ] **Scheduled auto-backup** (#29, 0.53.0). Today a backup is a manual export. Run the
      full backup on a schedule and keep the last N copies in the data
      folder; later, email it or send it to S3/Paperless (LubeLogger,
      MotoMate do this).
- [ ] **Fuelio and Drivvo import** (#27, 0.54.0). The big import sources still
      missing (Drivvo shows "Soon" in Settings). Needs a real export file of
      each as a fixture first.
- [ ] **More notification channels** (#28, 0.54.0): Discord, Gotify, Slack, Matrix next to
      email, ntfy, Pushover, webhook and Telegram.
- [ ] **OIDC/SSO sign-in** (#48, no target; Authelia, Authentik, Keycloak) for homelab users.
      Larger item: needs its own plan (account matching by email, registration
      mode, API keys stay local).
- [ ] **Receipt OCR** (#48, no target; local, optional) to prefill fuel and expense forms.
      Already named in the feature plan above.
- [ ] **VIN decode** (#48, no target; NHTSA, optional) to fill make, model and year.
- [ ] **Feature toggles** (#43, 0.54.0; Tracktor keeps five instance-wide toggles in its config table: fuel log, maintenance, compliance, reminders, overview, set from a Settings tab). Switch whole features (charging, trips, tires,
      documents) off so unused sections disappear (Tracktor). Menu visibility
      exists; this would also hide the data entry points.
- [ ] **Bulk actions** (#42, 0.54.0, after #29) on lists: duplicate, move to another vehicle, delete
      several (LubeLogger).
- [ ] **Custom fields** on records (#47, needs a design; LubeLogger).
- [ ] **Sale history PDF** (#45, help wanted) for selling a vehicle: all records in one report
      (MASHINA).
- [ ] **Tyre tread depth** measurements (#44, help wanted; not on the tire form today).
- [ ] **Kiosk / wall display** (#48, no target) view with live refresh (LubeLogger).
- [ ] **OpenAPI spec** (#46, help wanted) for the REST API.
- [ ] **Bangladesh paperwork types** (#39, 0.53.0; Tracktor already ships country-specific paperwork, India's pollution certificate, so the idea has a precedent). Add Tax Token, Fitness Certificate and
      Route Permit as reminder and document types (English names; the road tax
      and registration types are UK-flavoured today).
- [ ] **Driving Licence reminder and document type** (#40, 0.53.0, decide first). A licence belongs to a
      person, but a reminder needs a vehicle today (`vehicle_id` is required),
      so the simple version attaches it to the owner's main vehicle. Person-level
      reminders would be a larger change with a migration; decide before
      building. New type names need translations in every catalogue
      (`scripts/fill_po.py`).
- [ ] **Starter reminders for a new vehicle** (#41, 0.53.0). When a vehicle is added, offer
      to create its main paperwork reminders in one step (registration, tax,
      insurance, fitness) with their due dates.

- [ ] **Reminders by odometer as well as date, whichever comes first**
      (LubeLogger). A reminder here is date-only (`Reminder.due_date`); only
      maintenance schedules take kilometres. Check how much overlap there is
      before building.
- [ ] **Planner board** for upcoming work, as a kanban of planned, doing and
      done (LubeLogger). Needs a use case before a design.
- [ ] **Parts and supplies stock** that records can draw from (LubeLogger).
      OdoDash has Parts per vehicle; this would be stock across vehicles.
- [ ] **Dashboard widgets the user can rearrange** (Tracktor).
- [ ] **Fresh product screenshots.** The README and the landing page still
      show 0.49.0 (blue accent). Retake them in light, dark and phone.

Not planned for now: OBD2/Torque/WiCAN telemetry (MyGarage) and AI helpers,
which are far from the current scope.
