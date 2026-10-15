# Contributing to OdoDash 🚗💨

Welcome to OdoDash! This is a designer-led project, so alongside writing code, you have an equal opportunity to contribute through UI/UX improvements, animations, logo design, or feedback. Every contribution — big or small — helps make fleet management feel effortless.

## How to Contribute

### 1. Find or Open an Issue

Before starting work, comment on an existing issue or open a new one if you have an idea. Look especially for issues labelled:

- `good first issue` — great for newcomers
- `ux-enhancement` — design and interface improvements

This keeps work visible, avoids duplicated effort, and lets maintainers give early guidance.

### 2. Fork & Branch

Work in your own fork, and create a feature branch from `main`:

```bash
git checkout main
git pull upstream main
git checkout -b feature/gorgeous-modals
```

Use a short, descriptive branch name that reflects the change.

### 3. Coding Standards

- **Python / Flask**: Follow [PEP 8](https://peps.python.org/pep-0008/).
- **Frontend**: Use clean, semantic Tailwind CSS classes. Keep markup readable and avoid inline styles where a utility class will do.
- **Translations**: Commit `.po` files only. The compiled `messages.mo` files are build artefacts and are not tracked.
- **Commits**: Use the [Conventional Commits](https://www.conventionalcommits.org/) format (`feat:`, `fix:`, `docs:`, `chore:`, etc.).

### 4. Submitting a Pull Request (PR)

When you open a PR:

1. Give it a clear title and a description that explains *what* changed and *why*.
2. Use the repository's pull request template and fill in every section.
3. **For UI changes, before/after screenshots are required.** This is how we review visual work — a screenshot tells the story faster than a thousand words.
4. Reference the issue your PR closes (e.g. `Closes #12`).
5. Keep the change focused. One PR, one concern.

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
