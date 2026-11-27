# Contributing to OdoDash 🚗💨

Welcome to OdoDash! This is a designer-led project, so alongside writing code, you have an equal opportunity to contribute through UI/UX improvements, animations, logo design, or feedback. Every contribution — big or small — helps make fleet management feel effortless.

## How to Contribute

### 1. Find or Open an Issue

Before starting work, comment on an existing issue or open a new one if you have an idea. Look especially for issues labelled:

- `good first issue` — great for newcomers
- `ux-enhancement` — design and interface improvements

This keeps work visible, avoids duplicated effort, and lets maintainers give early guidance.

Comment and wait for a reply before you start. We take one pull request per issue, and an issue that someone has already claimed in a comment is theirs: a pull request for it will not be merged while that claim is active. A claim lapses after two weeks without activity.

### 2. Fork & Branch

Work in your own fork, and create a feature branch from **`dev`**. The default branch (`ododash-release`) is production and only receives changes through a pull request from `dev`, so please never target it directly.

```bash
git checkout dev
git pull upstream dev
git checkout -b feature/gorgeous-modals
```

Use a short, descriptive branch name that reflects the change.

### 3. Run it locally

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python scripts/build_css.py      # add --watch while editing templates
python run.py                    # login: admin / admin
pytest                           # run before you open a PR
```

### 4. Coding Standards

- **Python / Flask**: Follow [PEP 8](https://peps.python.org/pep-0008/). Look records up with `db.session.get(Model, id)` / `db.get_or_404(Model, id)`, and use `app.utils.utcnow()` instead of `datetime.utcnow()`. `tests/test_warning_hygiene.py` enforces both.
- **Database**: If you change a model, add a migration (`flask db migrate -m "..."`, then `flask db upgrade`) and commit it.
- **Frontend**: Build new UI from the macros in `app/templates/components/ui.html` and the `--ds-` tokens. Write Tailwind classes out in full (never `bg-{{ tone }}-100`); `tests/test_css_build.py` checks this. Admins can see every component at `/design`.
- **Translations**: Wrap user-facing text in `_()`. Regenerate the catalogue with `pybabel extract -F babel.cfg -k _l -o app/translations/messages.pot .` followed by `pybabel update ... -N`, and fill every language (`scripts/fill_po.py` shows what is missing). Commit `.po` files only; the compiled `messages.mo` files are not tracked.
- **Commits**: Use the [Conventional Commits](https://www.conventionalcommits.org/) format (`feat:`, `fix:`, `perf:`, `deps:`, `docs:`, `ci:`, `chore:`). No AI attribution lines such as `Co-Authored-By`.

### 5. Submitting a Pull Request (PR)

When you open a PR:

1. Open it against `dev`. Give it a clear title and a description that explains *what* changed and *why*.
2. Use the repository's pull request template and fill in every section.
3. **For UI changes, before/after screenshots are required.** This is how we review visual work — a screenshot tells the story faster than a thousand words.
4. Reference the issue your PR closes (e.g. `Closes #12`).
5. Keep the change focused. One PR, one concern.

### Using AI tools

AI coding tools are fine; the maintainer uses them too (see [AGENTS.md](../AGENTS.md)). What matters is that a person stands behind every pull request:

- You have read the change, run it yourself, run the tests, and can answer questions about it.
- One pull request is one issue you commented on first. Please do not open pull requests in bulk, or against issues nobody has asked you to take.
- You are around to answer review comments.

A pull request that nobody is answering for will be closed.

### What to expect

OdoDash is maintained by one person for now, so reviews can take a few days. A feature that was not discussed in an issue first may be declined even when the code is good, so please open an issue before starting anything large. Changes are tested on `dev` and reach production in the next release.

## Design & UX Contributions

OdoDash's core focus is a smoother, friendlier experience. If you're a designer, you can contribute by:

- Proposing improvements to forms, navigation, or dashboard layouts
- Refining typography, spacing, and color usage
- Designing icons, logos, or illustrations
- Sharing usability feedback or opening a `ux-enhancement` issue

When proposing a visual change, include a mockup or screenshot of the current state and your proposed state.

## Code of Conduct

All contributors are expected to follow our [Code of Conduct](../CODE_OF_CONDUCT.md). Be kind, be respectful, and help us keep this a welcoming community.

Thank you for helping make OdoDash better! ❤️
