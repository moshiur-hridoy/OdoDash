"""Add the per-account session token.

The values are filled in when the app starts (``_backfill_session_tokens``),
which also covers installs that never run ``flask db upgrade``.
"""
from alembic import op
import sqlalchemy as sa

revision = 'c4f7a1d9b802'
down_revision = 'a7c9e2f4b610'
branch_labels = None
depends_on = None


def upgrade():
    """Add the column unless schema bootstrap already added it."""
    if 'session_token' not in {c['name'] for c in sa.inspect(op.get_bind()).get_columns('users')}:
        with op.batch_alter_table('users') as batch:
            batch.add_column(sa.Column('session_token', sa.String(length=32), nullable=True))


def downgrade():
    """Remove the session token without changing other account data."""
    with op.batch_alter_table('users') as batch:
        batch.drop_column('session_token')
