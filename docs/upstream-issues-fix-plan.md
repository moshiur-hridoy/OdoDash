# Upstream Issue Fix Plan

This is a working checklist for reviewing selected open issues from
[dannymcc/may](https://github.com/dannymcc/may/issues) against this OdoDash
repository. The issue list and descriptions were reviewed on **2026-10-15**.
Issue status and upstream code may change; recheck both before starting work.

## How to use this plan

- Work on **one issue at a time**. Do not attempt to implement the whole plan in
  one task or batch unrelated issues together.
- Before coding, open the linked issue and read its latest comments, reproduce
  or verify the behavior in this repository, and inspect the relevant code and
  tests. Some upstream issues may already be fixed here or may describe behavior
  that differs from this fork.
- Agree on the issue's expected behavior and acceptance criteria before making
  changes, especially where the issue admits multiple reasonable designs.
- Make a focused change, add or update regression tests, and run the smallest
  relevant test set. Run additional database/backend checks when the issue
  requires them.
- Mark an issue complete only after its change and verification have passed.
  Record the exact validation command and outcome in the eventual PR or task
  summary. Keep unfinished items unchecked.
- Preserve existing OdoDash behavior and branding. Do not copy upstream changes
  blindly; adapt them to this repository.

## Status at a glance

Updated 2026-10-17. Released in v0.45.0 and v0.45.2.

| Issue | Status | Release |
| --- | --- | --- |
| #410 PostgreSQL upgrade | Fixed, needs live PostgreSQL check | v0.45.0 |
| #393 / #396 unit-price limit | Done | v0.45.0 |
| #390 SOC decimals | Done (whole numbers, clear error) | v0.45.2 |
| #395 document links | Done | v0.45.2 |
| #381 large numbers | Partly done; locale/mobile/PDF check open | v0.45.2 |
| #2 (this repo) total cost limit | Done, closed | v0.45.2 |
| #403, #384, #412, #371 | Not started | |
| #380, #382, #385/#406 | Not started | |
| #387, #413, #411, #360, #398, #386, #373, #268/#392 | Not started | |
| #397, #355 | Not started (outside the app) | |

## Phase 1 — Production bugs and data correctness

- [ ] **[dannymcc/may#410](https://github.com/dannymcc/may/issues/410) — PostgreSQL upgrade fails**
  _Status: fixed in v0.45.0, still open here until it is run on a real PostgreSQL._
  - [x] Reproduce the upgrade from the reported database revision on PostgreSQL
        and identify whether the failing `show_menu_tires` addition comes from
        the migration, startup schema recovery, or both.
        _Cause found by code analysis: startup schema recovery only; not
        reproduced on a live server._
  - [x] Make the boolean default portable to PostgreSQL without breaking SQLite
        or existing databases.
  - [ ] Add regression coverage for the relevant migration/startup path and
        verify upgrades on both supported database backends.
        _Unit test for the generated SQL exists; live PostgreSQL run pending._

- [ ] **[dannymcc/may#403](https://github.com/dannymcc/may/issues/403) — Recurring expenses create duplicates**
  - [ ] Reproduce using the latest issue details and inspect the recurring
        processor's behavior when invoked concurrently by multiple workers.
  - [ ] If concurrent duplicate creation is confirmed, make processing
        transaction-safe/idempotent (consider database constraints or locking
        appropriate to SQLite and PostgreSQL).
  - [ ] Add regression tests for repeated and concurrent processing. Do not
        silently delete existing expense records.

- [ ] **[dannymcc/may#384](https://github.com/dannymcc/may/issues/384) — Total distance differs from the odometer**
  - [ ] Define the intended total-distance calculation, including used vehicles,
        missing readings, engine-hour vehicles, and unit conversions.
  - [ ] Reconcile the calculation with the latest odometer sources already
        supported (fuel, trips, charging, expenses, and integrations).
  - [ ] Decide whether an explicit starting/purchase odometer is needed; avoid
        guessing a starting value from unrelated logs.
  - [ ] Add model and dashboard/vehicle-page regression tests for the agreed
        rules.

- [ ] **[dannymcc/may#412](https://github.com/dannymcc/may/issues/412) — EV overview is missing analysis**
  - [ ] Reproduce the report with trips and charging sessions, and identify
        which summary fields/charts are blank and why.
  - [ ] Check whether the distance calculation addressed in #384 is the cause;
        do not duplicate or conflict with that fix.
  - [ ] Correct EV overview calculations/display and test EVs with sparse,
        incomplete, and complete odometer/charging data.

- [x] **[dannymcc/may#390](https://github.com/dannymcc/may/issues/390) — Charging SOC does not accept decimals**
  - [x] Decide whether fractional SOC values are supported product behavior or
        whether the form should explicitly reject them with a visible error.
  - [x] If supported, update validation, database type/migration, UI input,
        serialization/API, and display consistently.
  - [x] Test decimal, integer, blank, out-of-range, create, and edit cases.

- [ ] **[dannymcc/may#371](https://github.com/dannymcc/may/issues/371) — Fuel price lookups fail**
  - [ ] Reproduce the reported stale/failed retailer feeds and station
        non-matching cases using current provider data where possible.
  - [ ] Ensure one failed feed does not prevent successful feeds from being
        processed; improve actionable diagnostics for matching failures.
  - [ ] Evaluate the UK Government Fuel Finder API as a provider option,
        including availability, authentication, data format, limits, and
        compatibility with existing saved stations.
  - [ ] Add tests for partial provider failure, postcode normalization, and
        matching. Keep any new provider isolated behind the existing service
        boundary.

## Phase 2 — Focused improvements

- [x] **[dannymcc/may#393](https://github.com/dannymcc/may/issues/393) and [#396](https://github.com/dannymcc/may/issues/396) — Fuel unit-price limit blocks high-denomination currencies**
  - [x] Treat these reports as one issue: check the limit in manual entry,
        edits, derived prices, discounts, and any related API paths.
  - [x] Replace the arbitrary limit with a safe, consistent validation rule
        that accepts legitimate high-denomination prices without permitting
        invalid numeric input.
  - [x] Add regression tests for values above 1,000 and for invalid/overflow
        values.

- [ ] **[dannymcc/may#380](https://github.com/dannymcc/may/issues/380) — Charging sessions that span midnight**
  - [ ] Define how session date, start date/time, and end date/time should be
        represented, including legacy records with only one date.
  - [ ] If an end date is required, add a backwards-compatible migration and
        update forms, validation, API/backup serialization, and duration logic.
  - [ ] Test sessions ending on the same day, the next day, and invalid or
        incomplete time/date combinations.

- [ ] **[dannymcc/may#382](https://github.com/dannymcc/may/issues/382) — Reuse charging locations**
  - [ ] Choose the smallest useful first release: duplicate a prior session with
        location/network/type prefilled, or create reusable location records.
  - [ ] If reusable records are chosen, define ownership/sharing and
        deletion/edit behavior before adding a model and CRUD UI.
  - [ ] Test that reusing a location/session does not duplicate the old
        charge's date, energy, cost, or odometer unintentionally.

- [ ] **[dannymcc/may#381](https://github.com/dannymcc/may/issues/381) — Improve readability of large numbers**
  - [x] Review large metrics and odometer/cost values in the dashboard, vehicle
        pages, lists, charts, and generated reports.
  - [x] Apply a consistent, legible numeric style and locale-aware grouping
        without changing stored values or number formatting semantics.
  - [ ] Verify representative locales, dark mode, mobile layouts, and PDFs.

- [x] **[dannymcc/may#395](https://github.com/dannymcc/may/issues/395) — Link to externally stored documents**
  - [x] Confirm which note fields should support links and whether plain URLs
        are sufficient for the first release.
  - [x] Render links safely (allow only approved URL schemes, escape text, and
        do not render unrestricted user HTML or Markdown).
  - [x] Test link display and editing across notes/expenses as applicable,
        including unsafe schemes and plain-text compatibility.

- [ ] **[dannymcc/may#385](https://github.com/dannymcc/may/issues/385) and [#406](https://github.com/dannymcc/may/issues/406) — Expense categories**
  - [ ] Decide whether MOT and Service are new categories or descriptive
        subtypes, and define how they relate to existing Inspection/Maintenance.
  - [ ] Add Car Payment as a category if confirmed, including recurring expenses.
  - [ ] Update every relevant surface: forms, filters, charts/reports,
        timelines, translations, exports, imports, API labels, and reminders.
  - [ ] Preserve old records and add coverage for category display and
        round-tripping.

## Phase 3 — Larger feature work

- [ ] **[dannymcc/may#387](https://github.com/dannymcc/may/issues/387) — Complete multiple maintenance items from one expense**
  - [ ] Define how one expense links to multiple schedules and how each
        schedule's performed date/odometer and event history are updated.
  - [ ] Add an appropriate relationship/migration and UI for selecting several
        eligible maintenance items.
  - [ ] Perform expense creation and maintenance updates atomically; test
        rollback, permissions, duplicate selection, and history.

- [ ] **[dannymcc/may#413](https://github.com/dannymcc/may/issues/413) — Support LFP charging without SOC-based assumptions**
  - [ ] Agree on charging concepts: full-charge anchor, partial/missed session,
        optional SOC, and how kWh consumption is calculated between anchors.
  - [ ] Reuse the proven fuel-log concepts where suitable without conflating
        fuel and electricity data.
  - [ ] Add any required model/API/UI migration compatibly and test LFP-style
        full charging with absent SOC, partial charges, missed sessions, and
        consumption intervals.

- [ ] **[dannymcc/may#411](https://github.com/dannymcc/may/issues/411) — Mileage-based reminders**
  - [ ] Compare the request with existing maintenance schedules, which already
        support date and odometer intervals, and determine whether that covers
        the user's general reminder use case.
  - [ ] If general reminders still need this, define baseline odometer,
        interval, vehicle units, recurrence, and “whichever comes first”
        behavior.
  - [ ] Add migrations, form/list/notification behavior, unit-conversion
        coverage, and recurrence tests only for the agreed scope.

- [ ] **[dannymcc/may#360](https://github.com/dannymcc/may/issues/360) — Per-user vehicle access and default vehicle**
  - [ ] Define how explicit sharing, instance-wide sharing, ownership, and
        default vehicle selection interact.
  - [ ] Add per-user access controls and/or a default-vehicle preference
        without breaking current sharing behavior.
  - [ ] Apply the same access rules to web routes, forms, reports, and APIs.
  - [ ] Test multiple users with overlapping vehicle access and safe fallback
        when a default vehicle is removed or access is revoked.

- [ ] **[dannymcc/may#398](https://github.com/dannymcc/may/issues/398) — Trailers and caravans**
  - [ ] Define a non-powered vehicle type and identify which screens/actions
        should remain available (expenses, maintenance, tires) versus hidden
        (fuel, charging, consumption).
  - [ ] Update model validation, forms, dashboard, API/import/export, and
        reports consistently.
  - [ ] Test existing powered vehicle behavior and trailer-specific flows.

- [ ] **[dannymcc/may#386](https://github.com/dannymcc/may/issues/386) — Import UK MOT history**
  - [ ] Verify current Government MOT API access requirements, eligibility,
        authentication, rate limits, and permitted data use.
  - [ ] Prototype a narrow read-only lookup and decide what history/advisories
        to store, refresh, and display.
  - [ ] Define how MOT expiry data interacts with existing DVLA fields and
        reminders before implementing persistence.
  - [ ] Add provider/service tests, failure handling, and user-facing tests.

- [ ] **[dannymcc/may#373](https://github.com/dannymcc/may/issues/373) — Estimate maintenance repair costs**
  - [ ] Verify dataset/API licensing, availability, vehicle/region coverage,
        update cadence, and whether estimates can be shown commercially.
  - [ ] If viable, design an optional integration and label results clearly as
        estimates—not logged expenses or guaranteed prices.
  - [ ] Test provider failures, unsupported vehicles/regions, and estimate
        display without affecting existing maintenance tracking.

- [ ] **[dannymcc/may#268](https://github.com/dannymcc/may/issues/268) and [#392](https://github.com/dannymcc/may/issues/392) — Fuel grade per fill-up**
  - [ ] Define the distinction between propulsion fuel (petrol/diesel/LPG/etc.)
        and grade (regular/premium, octane/cetane label), including hybrids.
  - [ ] Design backward-compatible storage and decide whether grade is
        free-form, a controlled list, or vehicle-configurable.
  - [ ] Update fuel entry/edit/quick entry, station prices/charts, API,
        imports/exports, translations, and reporting consistently.
  - [ ] Test legacy logs, mixed grades, hybrid fuel categorization, and
        filtering/aggregation.

## Outside the application runtime

- [ ] **[dannymcc/may#397](https://github.com/dannymcc/may/issues/397) — TrueNAS app catalog**
  - [ ] Review the current TrueNAS catalog contribution requirements and decide
        whether to submit a catalog app/chart.
  - [ ] Treat this as a packaging/deployment contribution, not an application
        feature; document image, storage, networking, upgrade, and support
        expectations.

- [ ] **[dannymcc/may#355](https://github.com/dannymcc/may/issues/355) — Stale local PR refs in the upstream harness**
  - [ ] Confirm whether this issue is still relevant in its intended
        harness/desk environment; it is not an OdoDash product-runtime issue.
  - [ ] Only an authorized maintainer in that environment should prune refs or
        change PR-fetch instructions. Do not delete local branches as part of
        an OdoDash code change.

## Completion record

For each completed issue, add a short entry here with the date, implementation
commit/PR, and exact test command(s) with results. Leave the issue checkbox
checked only while the fix remains verified and in the intended branch.

- 2026-10-16 — #393/#396: unit-price cap raised from 1,000 to `MAX_UNIT_PRICE` (1,000,000) in `app/routes/fuel.py`. `pytest tests/test_fuel.py tests/test_quick_fuel_prices.py` → 124 passed.
- 2026-10-17 — #390: SOC stays whole-number; decimals/out-of-range now rejected with a visible message (`parse_soc` in `app/routes/charging.py`). `pytest tests/test_charging.py` → 27 passed.
- 2026-10-17 — #381: tabular figures plus slight tracking for numbers (CSS in `base.html`). Visual change only; not checked in PDFs or across locales.
- 2026-10-17 — #395: `linkify` Jinja filter makes http(s) URLs in notes clickable (escaped, `rel="noopener noreferrer nofollow"`). `pytest tests/test_linkify.py` → 3 passed.
- 2026-10-17 — #2 (this repo): fuel total cost / sales tax limit raised to 1,000,000,000.
