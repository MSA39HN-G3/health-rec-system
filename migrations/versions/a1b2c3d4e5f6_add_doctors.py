"""add doctors

Revision ID: a1b2c3d4e5f6
Revises: fc1ad6bbf544
Create Date: 2026-07-03 18:30:00.000000

Tạo bảng doctors tách khỏi User (User là tài khoản đăng nhập, Doctor là hồ sơ
chuyên môn). Mỗi bác sĩ thuộc đúng một khoa qua FK department_id.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "fc1ad6bbf544"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "doctors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("department_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=64), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("doctors", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_doctors_department_id"), ["department_id"]
        )


def downgrade():
    with op.batch_alter_table("doctors", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_doctors_department_id"))
    op.drop_table("doctors")
