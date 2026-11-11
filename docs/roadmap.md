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

## Block D: small feature requests (target 0.48.x)

- [ ] **#420** Charging: derive price per kWh from total cost and energy.
- [ ] **#416** Fuel: separate loyalty-card discount on the total.
- [ ] **#385 / #406** Expense categories (Car Payment, MOT/Service). Upstream
      PR #407 is a candidate to adapt.

After Block D, return to the feature plan (Bangla translation, receipt scan,
insights).
