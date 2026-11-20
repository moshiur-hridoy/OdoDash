"""Remember completed loan payment history reviews."""
from alembic import op
import sqlalchemy as sa

revision = 'b74820c61ab3'
down_revision = 'd90837c5b024'
branch_labels = None
depends_on = None


def upgrade():
    if 'history_reviewed_on' not in {c['name'] for c in sa.inspect(op.get_bind()).get_columns('recurring_expenses')}:
        op.add_column('recurring_expenses', sa.Column('history_reviewed_on', sa.Date()))


def downgrade():
    with op.batch_alter_table('recurring_expenses') as batch:
        batch.drop_column('history_reviewed_on')
