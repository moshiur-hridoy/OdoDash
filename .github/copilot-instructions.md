# OdoDash: instructions for coding agents

Self-hosted vehicle manager (fuel, EV charging, expenses, maintenance, tyres,
trips, reminders), a fork of May. Flask (Python 3.12), SQLAlchemy with SQLite
(PostgreSQL optional), Jinja2 templates, Tailwind CSS compiled ahead of time,
Chart.js, WeasyPrint, Gunicorn, Flask-Migrate. The full rules are in
`CLAUDE.md` and `.github/CONTRIBUTING.md`; this file is the short version.
`AGENTS.md` and `.github/copilot-instructions.md` must stay identical
(`tests/test_agent_instructions.py` checks it).

## Branches and commits

- Work on `dev`. `ododash-release` is production and only receives a pull
  request from `dev`. Never push to `ododash-release` or `main`.
- Commit only when asked, and never push unless asked.
- Conventional Commits: `feat:`, `fix:`, `perf:`, `deps:`, `docs:`, `ci:`,
  `chore:`. One concern per commit. Reference an issue with `Closes #N`.
- Never add AI attribution to commits or pull requests: no `Co-Authored-By`,
  no "Generated with" lines.
- Open pull requests against `dev`. UI changes need before/after screenshots.
- Plan and ask before a large or risky change. Do not open issues or pull
  requests unless asked.

## Run and test

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python scripts/build_css.py      # builds app/static/css/app.css
python run.py                    # login: admin / admin
pytest                           # run before finishing; add a test for every fix
```

## Code rules (enforced by `tests/test_warning_hygiene.py`)

- Look records up with `db.session.get(Model, id)` and
  `db.get_or_404(Model, id)`, never `Model.query.get()`.
- Use `app.utils.utcnow()`, never `datetime.utcnow()`. It returns a naive UTC
  datetime on purpose.
- Changing a model needs a migration: `flask db migrate -m "..."`, then
  `flask db upgrade`. Commit the migration.
- Never commit secrets, a real `SECRET_KEY` or a `.env` file.

## Templates and styles

- Build new UI from the macros in `app/templates/components/ui.html` and the
  icons in `components/icons.html`; admins can see them all at `/design`.
  Wrap redesigned markup in `class="ds"` and use the `--ds-` tokens.
- Write Tailwind classes out in full. Never build one from template output
  (`bg-{{ tone }}-100`); `tests/test_css_build.py` checks this.
- Form controls stay plain HTML inside `field(...)` with `class="ds-control"`,
  so `name` and `id` are exactly what the route reads.
- Shell CSS uses logical sides (`inset-inline-start`), never `left`/`right`
  (`tests/test_app_shell.py`).
- `app/static/css/app.css` and the compiled `messages.mo` files are build
  artefacts and are not committed.

## Translations

- Wrap user-facing text in `_()` at the call site.
- Regenerate the catalogue from the repository root; keep `-k _l` and `-N`:

```bash
pybabel extract -F babel.cfg -k _l -o app/translations/messages.pot .
pybabel update -i app/translations/messages.pot -d app/translations --ignore-obsolete -N
pybabel compile -d app/translations
```

- Fill every language (`scripts/fill_po.py` lists what is missing). Commit
  `.po` files only. One English string means one sense.

## Docs

- Add a line to `CHANGELOG.md` under `[Unreleased]` for anything users will
  notice. Plans live in `docs/roadmap.md`.
- Write code, comments and docs in plain English.
