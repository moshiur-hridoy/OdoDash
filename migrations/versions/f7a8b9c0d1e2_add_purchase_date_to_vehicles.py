"""add purchase date to vehicles

Revision ID: f7a8b9c0d1e2
Revises: e1f2a3b4c5d6
Create Date: 2026-10-09

"""
from alembic import op
import sqlalchemy as sa


revision = 'f7a8b9c0d1e2'
down_revision = 'e1f2a3b4c5d6'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'vehicles' not in inspector.get_table_names():
        return
    columns = [column['name'] for column in inspector.get_columns('vehicles')]
    if 'purchase_date' not in columns:
        with op.batch_alter_table('vehicles', schema=None) as batch_op:
            batch_op.add_column(sa.Column('purchase_date', sa.Date(), nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'vehicles' not in inspector.get_table_names():
        return
    columns = [column['name'] for column in inspector.get_columns('vehicles')]
    if 'purchase_date' in columns:
        with op.batch_alter_table('vehicles', schema=None) as batch_op:
            batch_op.drop_column('purchase_date')
