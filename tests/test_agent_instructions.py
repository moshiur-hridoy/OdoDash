"""Copilot reads .github/copilot-instructions.md and Codex reads AGENTS.md.
They carry the same short rules, so one must never drift from the other."""
from pathlib import Path


def test_agent_instruction_files_are_identical():
    agents = Path('AGENTS.md').read_text()
    copilot = Path('.github/copilot-instructions.md').read_text()
    assert agents.strip()
    assert agents == copilot


def test_agent_instructions_keep_the_rules_that_matter():
    text = Path('AGENTS.md').read_text()
    for needle in ('db.session.get', 'utcnow', 'Co-Authored-By', 'ododash-release',
                   '-k _l', 'scripts/build_css.py'):
        assert needle in text
