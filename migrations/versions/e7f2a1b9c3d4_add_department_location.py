"""add department location

Revision ID: e7f2a1b9c3d4
Revises: d5e96480a32f
Create Date: 2026-06-30 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'e7f2a1b9c3d4'
down_revision = 'd5e96480a32f'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('departments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('location', sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table('departments', schema=None) as batch_op:
        batch_op.drop_column('location')
