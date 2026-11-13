# OdoDash 🚗💨

*A gorgeous, self-hosted vehicle management dashboard optimized for the ultimate user experience. Track fuel, expenses, maintenance, and trips without the clutter.*

> 💡 **Notice:** OdoDash is an actively maintained, designer-led friendly fork of the wonderful [May](https://github.com/dannymcc/may) project by [Danny McClelland](https://github.com/dannymcc). We are deeply grateful for the foundational codebase. This fork is dedicated to continuous UX/UI enhancements, active bug fixes, and community-driven features.

![Flask](https://img.shields.io/badge/Flask-Python-blue) ![GitHub Release](https://img.shields.io/github/v/release/moshiur-hridoy/OdoDash) ![License](https://img.shields.io/badge/license-MIT-green) ![Docker](https://img.shields.io/badge/Docker-Ready-2496ED) ![PWA](https://img.shields.io/badge/PWA-Ready-5A0FC8)

## Why OdoDash

OdoDash tracks fuel, expenses, reminders and maintenance across your whole fleet. The original May project is an excellent backend; OdoDash adds a simpler, more modern and more responsive interface on top.

- **Designer-led UX/UI:** flat, hairline-bordered cards, refined typography and a shared chart theme in light and dark.
- **Your colour:** pick an accent from a suggested palette (or any colour) and text stays readable on it.
- **Streamlined logging:** fuel and expense forms need fewer clicks, with limits checked as you type.
- **Mobile and PWA:** app-like navigation on phones.
- **Active maintenance:** upstream bugs and useful PRs are merged here quickly.

<p align="center">
  <a href="https://ododashdemo.moshiur.space/"><b>Try the live demo</b></a> (login <code>demo</code> / <code>demo</code>, resets nightly) · <a href="https://moshiur-hridoy.github.io/OdoDash/">Website</a>
</p>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="screenshots/dashboard-dark.png">
    <img src="screenshots/dashboard-light.png" alt="OdoDash dashboard" width="100%">
  </picture>
</p>

## A quick look

### Light and dark, your way

Both themes share one design system, so nothing looks bolted on.

<table>
  <tr>
    <td width="50%"><img src="screenshots/dashboard-light.png" alt="Dashboard in light mode"><br><sub><b>Light.</b> Quiet surfaces with hairline borders.</sub></td>
    <td width="50%"><img src="screenshots/dashboard-dark.png" alt="Dashboard in dark mode"><br><sub><b>Dark.</b> Soft depth that is easy on the eyes at night.</sub></td>
  </tr>
</table>

### Make it yours

Choose an accent colour once and the whole interface follows: buttons, charts and highlights. Admins can also set the app name, tagline and logo.

<table>
  <tr>
    <td width="50%"><img src="screenshots/accent-color.png" alt="Dashboard with an orange accent colour"><br><sub><b>Any accent.</b> The same dashboard in orange.</sub></td>
    <td width="50%"><img src="screenshots/branding.png" alt="Branding settings with a colour palette"><br><sub><b>Branding.</b> A suggested palette, or a custom colour.</sub></td>
  </tr>
</table>

### Every vehicle at a glance

<p align="center">
  <img src="screenshots/vehicle-page.png" alt="Vehicle page with stats and quick actions" width="100%">
</p>

Costs, distance, consumption and CO&#8322; sit in one place, with quick actions to log fuel, trips, expenses and reminders, and shortcuts to maintenance history, parts and the timeline.

### Made for the phone in your pocket

A bottom tab bar, a big add button and forms that fit one thumb, so logging a fill-up at the pump takes seconds. Nothing scrolls sideways.

<table>
  <tr>
    <td width="33%"><img src="screenshots/mobile-dashboard.png" alt="Dashboard on a phone"><br><sub><b>Dashboard.</b> This month at a glance.</sub></td>
    <td width="33%"><img src="screenshots/mobile-vehicle.png" alt="Vehicle page on a phone in dark mode"><br><sub><b>Vehicle.</b> Odometer, consumption and cost per km.</sub></td>
    <td width="33%"><img src="screenshots/mobile-add-fuel.png" alt="Add Fuel Log form on a phone"><br><sub><b>Add fuel.</b> Pick a car, type the reading, save.</sub></td>
  </tr>
</table>

### Settings that stay out of the way

<p align="center">
  <img src="screenshots/settings.png" alt="Units and values settings in dark mode" width="100%">
</p>

Units, currency, date format and language are per user, so a household can mix kilometres and miles, litres and gallons.

## How it relates to May

OdoDash started as a fork of [May](https://github.com/dannymcc/may) and keeps its data model, REST API and import format, so May backups restore directly. On top of that foundation OdoDash adds:

- A redesigned interface: hairline cards, a shared chart theme, light and dark.
- A custom accent colour with readable text on it.
- Logging forms with fewer clicks and limits checked as you type.
- A built-in public demo mode with seeded data (see the [demo guide](docs/demo.md)).
- Upstream bug fixes and useful PRs merged quickly.

Looking at other self-hosted options? [LubeLogger](https://github.com/hargata/lubelog) and [Hammond](https://github.com/AlfHou/hammond) are worth a look too. Pick the one whose interface and feature set suit you.

## Features

- 🚗 **Multi-vehicle:** cars, vans, motorbikes and scooters, shared between users with roles
- ⛽ **Fuel and EV charging:** automatic consumption (L/100km, MPG), quick entry mode, favourite stations
- 💰 **Expenses:** by category, plus recurring payments such as insurance and tax
- 🔧 **Maintenance and tires:** schedules by mileage, hours or date, with tire set history
- 🧭 **Trips and reminders:** mileage logs, MOT/service/tax reminders by email, ntfy, Pushover or webhook
- 📁 **Documents and receipts:** attach files to vehicles, fuel logs and expenses
- 📊 **Analytics and PDF reports:** spending trends, consumption charts, printable vehicle reports
- 🎨 **Customisable:** dark mode, branding, units, many currencies and 20 languages
- 🔌 **Integrations:** REST API, Home Assistant, calendar subscription, UK fuel prices, DVLA lookup
- 📥 **Import and export:** May backups, Fuelly CSV, JSON and CSV export
- 🐳 **Self-hosted:** Docker and PWA ready

## Quick Start

```bash
git clone https://github.com/moshiur-hridoy/OdoDash.git
cd OdoDash
docker compose up -d
```

Open `http://localhost:5050` and sign in as `admin`. Unless you set `ADMIN_PASSWORD`, the generated password is printed once in the logs (`docker logs ododash`). Change it after your first login.

Without Docker:

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
pybabel compile -d app/translations
python run.py
```

More options (plain `docker run`, first-login details) are in the [installation guide](docs/installation.md).

## Documentation

| Guide | Contents |
| --- | --- |
| [Installation](docs/installation.md) | Docker, Compose, manual install, first login |
| [Configuration](docs/configuration.md) | `.env`, environment variables, PUID/PGID |
| [Usage](docs/usage.md) | Every feature, from fuel logs to import and restore |
| [Administration](docs/administration.md) | Admin settings, user roles, REST API |
| [Integrations](docs/integrations.md) | UK fuel prices, Home Assistant, calendar |
| [Languages](docs/translations.md) | Supported languages, improving and adding translations |
| [Troubleshooting](docs/troubleshooting.md) | Common problems and fixes |
| [Changelog](CHANGELOG.md) | What changed in each release |

## Tech Stack

Python / Flask, SQLite or PostgreSQL, Tailwind CSS, HTMX, Chart.js, Gunicorn, WeasyPrint.

## Contributing

Contributions are welcome. OdoDash is a designer-led project, so UI/UX ideas, animations, logo design and feedback are as valuable as code. Please read [CONTRIBUTING.md](.github/CONTRIBUTING.md) first. Report bugs and ideas in [GitHub Issues](https://github.com/moshiur-hridoy/OdoDash/issues).

## License and Acknowledgments

MIT License, see [LICENSE](LICENSE). The original May project is Copyright (c) 2026 Danny McClelland.

- Original project: [May](https://github.com/dannymcc/may) by [Danny McClelland](https://github.com/dannymcc)

---

**OdoDash is a fork of [May](https://github.com/dannymcc/may), created by [Danny McClelland](https://github.com/dannymcc). Redesigned and maintained by [moshiur-hridoy](https://github.com/moshiur-hridoy).**
