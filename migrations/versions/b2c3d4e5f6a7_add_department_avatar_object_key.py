"""add department avatar_object_key

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-04 10:00:00.000000

Bổ sung cột `departments.avatar_object_key` (VARCHAR 512, nullable) để lưu
object key từ Cloudflare R2 thay vì lưu thẳng URL (tránh URL hết hạn).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    # pylint: disable=no-member  (alembic.op là dynamic, pylint giải không ra)
    with op.batch_alter_table("departments", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("avatar_object_key", sa.String(length=512), nullable=True)
        )


def downgrade():
    # pylint: disable=no-member
    with op.batch_alter_table("departments", schema=None) as batch_op:
        batch_op.drop_column("avatar_object_key")
