"""drop head_doctor_id on departments + drop role doctor

Refactor lớn: bỏ khái niệm "trưởng khoa là một user/doctor cụ thể". Cụ thể:

1. Bỏ cột ``departments.head_doctor_id`` (cũ là FK tới ``users.id``).
   - Lý do nghiệp vụ: trưởng khoa nên tham chiếu tới entity ``doctors`` (bác sĩ
     thuộc khoa), không phải tài khoản user — và vì ``staff`` giờ quản lý tất
     cả bác sĩ nên khái niệm "trưởng khoa = user-id" không còn phù hợp.
   - Dữ liệu cũ trên cột này (nếu có) sẽ bị mất — chấp nhận theo yêu cầu
     product (xem `docs/FE_DEPARTMENT.md`).

2. Bỏ role ``doctor`` trong bảng ``roles``.
   - Lý do: role doctor trên ``users`` không còn ý nghĩa vì "ai là bác sĩ" giờ
     được xác định qua bảng ``doctors`` (entity chuyên môn tách khỏi tài khoản).
   - Cascade xóa các ``user_roles`` và ``role_permissions`` tham chiếu role này.

3. Bỏ 3 i18n key liên quan tới head-doctor (``head_doctor_not_found``,
   ``head_doctor_not_doctor``, ``head_required_when_active``) — việc này FE/BE
   sẽ xử lý qua cleanup code (xoá ở ``app/i18n/locales/*.json``), không
   migration nào chạm JSON.

Downgrade: no-op an toàn (column + role đã xóa; downgrade chỉ in cảnh báo).

Revision ID: 1a2b3c4d5e6f
Revises: 8b9c0d1e2f3a
Create Date: 2026-07-12 11:30:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1a2b3c4d5e6f"
down_revision = "8b9c0d1e2f3a"
branch_labels = None
depends_on = None


ROLE_DOCTOR = "doctor"


def upgrade():
    conn = op.get_bind()

    # ------------------------------------------------------------------ #
    # 1) Drop cột head_doctor_id trên departments.                       #
    #    PostgreSQL tự động drop FK constraint trỏ vào cột này khi drop #
    #    cột; nếu DB khác cần drop constraint trước.                    #
    # ------------------------------------------------------------------ #
    with op.batch_alter_table("departments", schema=None) as batch_op:
        batch_op.drop_column("head_doctor_id")

    # ------------------------------------------------------------------ #
    # 2) Drop role ``doctor`` nếu còn tồn tại (kèm cascade FK).         #
    # ------------------------------------------------------------------ #
    roles = sa.table(
        "roles",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
    )
    user_roles = sa.table(
        "user_roles",
        sa.column("user_id", sa.Integer),
        sa.column("role_id", sa.Integer),
    )
    role_permissions = sa.table(
        "role_permissions",
        sa.column("role_id", sa.Integer),
        sa.column("permission_id", sa.Integer),
    )

    doctor_role_id = conn.execute(
        sa.select(roles.c.id).where(roles.c.name == ROLE_DOCTOR)
    ).scalar()
    if doctor_role_id is not None:
        # Cascade cleanup các bảng trung gian trước khi drop role.
        conn.execute(
            user_roles.delete().where(user_roles.c.role_id == doctor_role_id)
        )
        conn.execute(
            role_permissions.delete().where(
                role_permissions.c.role_id == doctor_role_id
            )
        )
        conn.execute(roles.delete().where(roles.c.id == doctor_role_id))


def downgrade():
    # Refactor này không thể rollback sạch — thông tin head_doctor_id cũ
    # đã mất, mapping user_id -> doctor entity cũng không khôi phục được.
    # Downgrade chỉ là no-op kèm log cảnh báo.
    import logging

    logging.getLogger("alembic.env").warning(
        "downgrade() của 1a2b3c4d5e6f là no-op: cột head_doctor_id và role "
        "doctor đã bị xóa. Nếu cần khôi phục, hãy seed lại thủ công và viết "
        "migration riêng (không rollback tự động được)."
    )
    return