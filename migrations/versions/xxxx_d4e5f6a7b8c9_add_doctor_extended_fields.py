"""add_doctor_extended_fields

Revision ID: xxxx_d4e5f6a7b8c9
Revises: 0adf3e3f6a25
Create Date: 2026-07-09 16:30:00.000000

Mở rộng bảng doctors với:
- Phần 1: Thông tin cá nhân (phone, email, avatar, date_of_birth, gender, address)
- Phần 2: Thông tin chuyên môn (license_number, license_issue_date, license_expiry_date,
  specialization, sub_specializations, education, experience_years, training_institutions)
- Phần 5: Thông tin hành chính (employment_type, hire_date, contract_end_date,
  is_accepting_new_patients)
- Phần 6: Bảng doctor_documents (quản lý tài liệu)
- Phần 7: Bảng doctor_statistics (thống kê) và doctor_ratings (đánh giá)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "xxxx_d4e5f6a7b8c9"
down_revision = "0adf3e3f6a25"
branch_labels = None
depends_on = None


def upgrade():
    # === Mở rộng bảng doctors (dùng batch mode cho simple columns) ===
    with op.batch_alter_table("doctors", schema=None) as batch_op:
        # Phần 1: Thông tin cá nhân
        batch_op.add_column(sa.Column("phone", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("email", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("avatar_object_key", sa.String(length=512), nullable=True))
        batch_op.add_column(sa.Column("avatar_url", sa.String(length=512), nullable=True))
        batch_op.add_column(sa.Column("date_of_birth", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("gender", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("address", sa.Text(), nullable=True))

        # Phần 2: Thông tin chuyên môn (simple columns)
        batch_op.add_column(sa.Column("license_number", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("license_issue_date", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("license_expiry_date", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("specialization", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("experience_years", sa.Integer(), nullable=True))

        # Phần 5: Thông tin hành chính
        batch_op.add_column(sa.Column("employment_type", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("hire_date", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("contract_end_date", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("is_accepting_new_patients", sa.Boolean(), server_default="true", nullable=False))

    # Thêm ARRAY columns riêng (không dùng batch mode vì PostgreSQL limitation)
    op.add_column("doctors", sa.Column("sub_specializations", postgresql.ARRAY(sa.String(length=255)), server_default="{}"))
    op.add_column("doctors", sa.Column("education", postgresql.ARRAY(sa.String(length=255)), server_default="{}"))
    op.add_column("doctors", sa.Column("training_institutions", postgresql.ARRAY(sa.String(length=255)), server_default="{}"))

    # === Tạo bảng doctor_documents ===
    op.create_table(
        "doctor_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("doctor_id", sa.Integer(), nullable=False),
        sa.Column("document_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=True),
        sa.Column("url", sa.String(length=512), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("is_verified", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("doctor_documents", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_doctor_documents_doctor_id"), ["doctor_id"])

    # === Tạo bảng doctor_statistics ===
    op.create_table(
        "doctor_statistics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("doctor_id", sa.Integer(), nullable=False),
        sa.Column("total_appointments", sa.Integer(), server_default="0", nullable=False),
        sa.Column("completed_appointments", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cancelled_appointments", sa.Integer(), server_default="0", nullable=False),
        sa.Column("average_rating", sa.Float(), nullable=True),
        sa.Column("total_ratings", sa.Integer(), server_default="0", nullable=False),
        sa.Column("average_consultation_time_minutes", sa.Integer(), nullable=True),
        sa.Column("patient_satisfaction_score", sa.Float(), nullable=True),
        sa.Column("last_calculated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("doctor_id", name="uq_doctor_statistics_doctor"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("doctor_statistics", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_doctor_statistics_doctor_id"), ["doctor_id"])

    # === Tạo bảng doctor_ratings ===
    op.create_table(
        "doctor_ratings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("doctor_id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("appointment_id", sa.Integer(), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("appointment_id", name="uq_doctor_rating_appointment"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("doctor_ratings", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_doctor_ratings_doctor_id"), ["doctor_id"])
        batch_op.create_index(batch_op.f("ix_doctor_ratings_patient_id"), ["patient_id"])


def downgrade():
    # === Xóa bảng doctor_ratings ===
    with op.batch_alter_table("doctor_ratings", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_doctor_ratings_patient_id"))
        batch_op.drop_index(batch_op.f("ix_doctor_ratings_doctor_id"))
    op.drop_table("doctor_ratings")

    # === Xóa bảng doctor_statistics ===
    with op.batch_alter_table("doctor_statistics", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_doctor_statistics_doctor_id"))
    op.drop_table("doctor_statistics")

    # === Xóa bảng doctor_documents ===
    with op.batch_alter_table("doctor_documents", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_doctor_documents_doctor_id"))
    op.drop_table("doctor_documents")

    # Xóa ARRAY columns trước
    op.drop_column("doctors", "training_institutions")
    op.drop_column("doctors", "education")
    op.drop_column("doctors", "sub_specializations")

    # === Xóa các cột mới của bảng doctors ===
    with op.batch_alter_table("doctors", schema=None) as batch_op:
        batch_op.drop_column("is_accepting_new_patients")
        batch_op.drop_column("contract_end_date")
        batch_op.drop_column("hire_date")
        batch_op.drop_column("employment_type")
        batch_op.drop_column("experience_years")
        batch_op.drop_column("specialization")
        batch_op.drop_column("license_expiry_date")
        batch_op.drop_column("license_issue_date")
        batch_op.drop_column("license_number")
        batch_op.drop_column("address")
        batch_op.drop_column("gender")
        batch_op.drop_column("date_of_birth")
        batch_op.drop_column("avatar_url")
        batch_op.drop_column("avatar_object_key")
        batch_op.drop_column("email")
        batch_op.drop_column("phone")
