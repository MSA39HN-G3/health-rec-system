"""merge department_head role into staff

Sau refactor: ``department_head`` đã được gộp vào ``staff`` (staff giờ là cả
department_head, trưởng khoa + nhân viên lễ tân/điều dưỡng).

Công việc của migration này:
  1. Tìm id của role ``department_head`` (nếu tồn tại) và role ``staff``.
  2. Tạo role ``staff`` nếu chưa có (seed ngược cho môi trường cũ).
  3. Với mọi user_roles liên kết với role ``department_head``:
       - Nếu user đó CHƯA có role ``staff`` → thêm vào.
       - Sau đó xóa liên kết với ``department_head``.
  4. Xóa các role_permissions trỏ vào role ``department_head``.
  5. Xóa role ``department_head``.

Downgrade: migration này không thể rollback hoàn toàn (vì lịch sử ai đó là
trưởng khoa có thể đã mất), downgrade chỉ là no-op và in cảnh báo.

Revision ID: 6e7f8a9b0c1d
Revises: 16437349b16a, c447d587eb9b
Create Date: 2026-07-12 08:35:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6e7f8a9b0c1d"
# Merge 2 heads: 'health_record_symptoms' và 'recommendations'.
down_revision = ("16437349b16a", "c447d587eb9b")
branch_labels = ("merge-dept-head",)
depends_on = None


# Tên role chuẩn trong DB.
ROLE_DEPARTMENT_HEAD = "department_head"
ROLE_STAFF = "staff"


def upgrade():
    conn = op.get_bind()

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

    # 1. Lấy id của 2 role nếu tồn tại.
    dh_id = conn.execute(
        sa.select(roles.c.id).where(roles.c.name == ROLE_DEPARTMENT_HEAD)
    ).scalar()
    if dh_id is None:
        # Role đã được xóa từ trước (vd clean DB) -> không có gì để migrate.
        return

    staff_id = conn.execute(
        sa.select(roles.c.id).where(roles.c.name == ROLE_STAFF)
    ).scalar()
    if staff_id is None:
        # Tạo role staff với permission rỗng — permission sẽ được default
        # seed chạy ở bước tiếp theo (nếu app có seed CLI).
        result = conn.execute(
            roles.insert().values(name=ROLE_STAFF, description="Staff (gồm cả trưởng khoa)")
        )
        staff_id = result.inserted_primary_key[0]

    # 2. Tìm tất cả user đang có role department_head.
    dh_user_ids = [
        row[0]
        for row in conn.execute(
            sa.select(user_roles.c.user_id).where(user_roles.c.role_id == dh_id)
        ).fetchall()
    ]

    # 3. Với từng user: nếu chưa có role staff thì thêm vào.
    if dh_user_ids:
        existing_staff_user_ids = {
            row[0]
            for row in conn.execute(
                sa.select(user_roles.c.user_id).where(
                    sa.and_(
                        user_roles.c.role_id == staff_id,
                        user_roles.c.user_id.in_(dh_user_ids),
                    )
                )
            ).fetchall()
        }
        new_assignments = [
            {"user_id": uid, "role_id": staff_id}
            for uid in dh_user_ids
            if uid not in existing_staff_user_ids
        ]
        if new_assignments:
            conn.execute(user_roles.insert(), new_assignments)

        # 4. Xóa các liên kết user <-> department_head.
        conn.execute(
            user_roles.delete().where(user_roles.c.role_id == dh_id)
        )

    # 5. Xóa role_permissions còn trỏ vào department_head.
    conn.execute(
        role_permissions.delete().where(role_permissions.c.role_id == dh_id)
    )

    # 6. Xóa role department_head.
    conn.execute(roles.delete().where(roles.c.id == dh_id))


def downgrade():
    # Refactor này không thể rollback sạch — lịch sử "trưởng khoa" có thể
    # đã hoàn toàn gộp vào staff và không phân biệt lại được. Downgrade chỉ
    # là no-op kèm log để người vận hành biết phải chạy thủ công seed lại
    # role department_head nếu thật sự cần.
    import logging

    logging.getLogger("alembic.env").warning(
        "downgrade() của 6e7f8a9b0c1d là no-op: role department_head đã được "
        "gộp vào staff và không thể tách lại an toàn. Nếu cần role này trở lại, "
        "hãy chạy seed/CLI thủ công."
    )
    return
