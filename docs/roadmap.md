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

After Block D, return to the feature plan (Bangla translation, receipt scan,
insights).
