"""Store optional fixed-rate terms on schedules and individual payments."""
from alembic import op
import sqlalchemy as sa

revision = 'd90837c5b024'
down_revision = 'a7c9e2f4b610'
branch_labels = None
depends_on = None


def upgrade():
    for table in ('expenses', 'recurring_expenses'):
        if 'loan_terms' not in {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}:
            op.add_column(table, sa.Column('loan_terms', sa.JSON(none_as_null=True), nullable=True))


def downgrade():
    for table in ('expenses', 'recurring_expenses'):
        with op.batch_alter_table(table) as batch:
            batch.drop_column('loan_terms')
