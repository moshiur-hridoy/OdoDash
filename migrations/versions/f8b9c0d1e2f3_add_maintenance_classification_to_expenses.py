"""add maintenance classification to expenses

Revision ID: f8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-10-09

"""
from alembic import op
import sqlalchemy as sa


revision = 'f8b9c0d1e2f3'
down_revision = 'f7a8b9c0d1e2'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'expenses' not in inspector.get_table_names():
        return
    columns = [column['name'] for column in inspector.get_columns('expenses')]
    additions = []
    if 'maintenance_group' not in columns:
        additions.append(sa.Column('maintenance_group', sa.String(length=20), nullable=True))
    if 'maintenance_part' not in columns:
        additions.append(sa.Column('maintenance_part', sa.String(length=100), nullable=True))
    if additions:
        with op.batch_alter_table('expenses', schema=None) as batch_op:
            for column in additions:
                batch_op.add_column(column)

    expenses = sa.table(
        'expenses',
        sa.column('id', sa.Integer()),
        sa.column('category', sa.String()),
        sa.column('description', sa.String()),
        sa.column('maintenance_group', sa.String()),
        sa.column('maintenance_part', sa.String()),
    )
    rows = bind.execute(sa.select(expenses).where(
        expenses.c.category == 'maintenance',
        expenses.c.maintenance_group.is_(None),
    )).mappings()
    for row in rows:
        description = (row['description'] or '').lower()
        if any(term in description for term in ('engine oil', 'oil change', 'synthetic oil', 'motor oil')):
            group, part = 'engine_oil', None
        elif any(term in description for term in ('brake', 'filter', 'spark plug', 'battery', 'tyre', 'tire', 'chain', 'coolant')):
            group, part = 'parts', row['description']
        elif any(term in description for term in ('service', 'servicing', 'workshop', 'maintenance')):
            group, part = 'servicing', None
        else:
            continue
        bind.execute(expenses.update().where(expenses.c.id == row['id']).values(
            maintenance_group=group, maintenance_part=part))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'expenses' not in inspector.get_table_names():
        return
    columns = [column['name'] for column in inspector.get_columns('expenses')]
    with op.batch_alter_table('expenses', schema=None) as batch_op:
        if 'maintenance_part' in columns:
            batch_op.drop_column('maintenance_part')
        if 'maintenance_group' in columns:
            batch_op.drop_column('maintenance_group')
