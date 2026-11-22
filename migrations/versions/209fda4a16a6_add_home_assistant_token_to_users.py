"""home assistant token

Revision ID: 209fda4a16a6
Revises: b0d1e2f3a4b5
Create Date: 2026-11-20

"""
from alembic import op
import sqlalchemy as sa


revision = '209fda4a16a6'
down_revision = 'b0d1e2f3a4b5'
branch_labels = None
depends_on = None

COLUMNS = (
    ('ha_token', sa.String(length=64)),
    ('ha_token_created_at', sa.DateTime()),
)
INDEX = 'ix_users_ha_token'


def _existing(bind, table):
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return None, None
    columns = {c['name'] for c in inspector.get_columns(table)}
    indexes = {i['name'] for i in inspector.get_indexes(table)}
    return columns, indexes


def upgrade():
    # Startup schema recovery may already have added these columns, so each
    # step checks before acting.
    bind = op.get_bind()
    columns, _ = _existing(bind, 'users')
    if columns is None:
        return
    missing = [(name, type_) for name, type_ in COLUMNS if name not in columns]
    if missing:
        with op.batch_alter_table('users', schema=None) as batch_op:
            for name, type_ in missing:
                batch_op.add_column(sa.Column(name, type_, nullable=True))
    _, indexes = _existing(bind, 'users')
    if INDEX not in indexes:
        op.create_index(INDEX, 'users', ['ha_token'], unique=True)


def downgrade():
    bind = op.get_bind()
    columns, indexes = _existing(bind, 'users')
    if columns is None:
        return
    if INDEX in indexes:
        op.drop_index(INDEX, table_name='users')
    present = [name for name, _ in COLUMNS if name in columns]
    if present:
        with op.batch_alter_table('users', schema=None) as batch_op:
            for name in present:
                batch_op.drop_column(name)
