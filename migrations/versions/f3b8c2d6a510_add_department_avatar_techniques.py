"""add department avatar_url and techniques

Revision ID: f3b8c2d6a510
Revises: e7f2a1b9c3d4
Create Date: 2026-06-30 00:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'f3b8c2d6a510'
down_revision = 'e7f2a1b9c3d4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('departments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('avatar_url', sa.String(length=512), nullable=True))
        batch_op.add_column(sa.Column(
            'techniques',
            postgresql.ARRAY(sa.String(length=255)),
            server_default='{}',
            nullable=False,
        ))


def downgrade():
    with op.batch_alter_table('departments', schema=None) as batch_op:
        batch_op.drop_column('techniques')
        batch_op.drop_column('avatar_url')
