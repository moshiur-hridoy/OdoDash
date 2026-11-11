"""add telegram link to users

Revision ID: a9c0d1e2f3a4
Revises: f8b9c0d1e2f3
Create Date: 2026-11-12

"""
from alembic import op
import sqlalchemy as sa


revision = 'a9c0d1e2f3a4'
down_revision = 'f8b9c0d1e2f3'
branch_labels = None
depends_on = None

COLUMNS = (
    ('telegram_chat_id', sa.String(length=32)),
    ('telegram_link_code', sa.String(length=16)),
    ('telegram_link_expires', sa.DateTime()),
)
UNIQUE_INDEXED = ('telegram_chat_id', 'telegram_link_code')


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
    for name in UNIQUE_INDEXED:
        index_name = f'ix_users_{name}'
        if index_name not in indexes:
            op.create_index(index_name, 'users', [name], unique=True)


def downgrade():
    bind = op.get_bind()
    columns, indexes = _existing(bind, 'users')
    if columns is None:
        return
    for name in UNIQUE_INDEXED:
        index_name = f'ix_users_{name}'
        if index_name in indexes:
            op.drop_index(index_name, table_name='users')
    present = [name for name, _ in COLUMNS if name in columns]
    if present:
        with op.batch_alter_table('users', schema=None) as batch_op:
            for name in present:
                batch_op.drop_column(name)
