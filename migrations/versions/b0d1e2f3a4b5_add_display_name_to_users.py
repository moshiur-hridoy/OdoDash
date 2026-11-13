"""add display name to users

Revision ID: b0d1e2f3a4b5
Revises: a9c0d1e2f3a4
Create Date: 2026-11-13

"""
from alembic import op
import sqlalchemy as sa


revision = 'b0d1e2f3a4b5'
down_revision = 'a9c0d1e2f3a4'
branch_labels = None
depends_on = None


def _columns(bind):
    inspector = sa.inspect(bind)
    if 'users' not in inspector.get_table_names():
        return None
    return {c['name'] for c in inspector.get_columns('users')}


def upgrade():
    # Startup schema recovery may already have added the column.
    columns = _columns(op.get_bind())
    if columns is None or 'display_name' in columns:
        return
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('display_name', sa.String(length=64), nullable=True))


def downgrade():
    columns = _columns(op.get_bind())
    if columns is None or 'display_name' not in columns:
        return
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('display_name')
