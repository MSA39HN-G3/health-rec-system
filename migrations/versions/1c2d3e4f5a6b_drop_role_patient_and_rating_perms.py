"""drop role patient + 3 permission rating:* + drop rating tables/columns

Refactor 1c2d3e4f5a6b: bỏ toàn bộ tính năng đánh giá bác sĩ + bỏ role ``patient``.

Lý do nghiệp vụ:
  - Bệnh nhân không còn đăng nhập/đánh giá trên hệ thống (sản phẩm hiện chỉ phục
    vụ nhân viên + admin).
  - Theo đó, role ``patient`` và 3 permission ``rating:read``, ``rating:write``,
    ``rating:manage`` không còn ý nghĩa. Toàn bộ code đã được dọn (xóa model
    DoctorRating, repository, service, controller blueprint).

Migration này:
  1. Drop bảng ``doctor_ratings`` (bảng chính lưu đánh giá).
  2. Drop cột ``average_rating``, ``total_ratings`` trên ``doctor_statistics``
     (dữ liệu rỗng nên an toàn — stats service không còn ghi các cột này).
  3. Cascade xóa ``user_roles`` + ``role_permissions`` tham chiếu role ``patient``.
  4. Xóa role ``patient``.
  5. Cascade xóa ``role_permissions`` tham chiếu 3 permission ``rating:*``.
  6. Xóa 3 permission ``rating:read``, ``rating:write``, ``rating:manage``.

Lưu ý:
  - DB test/dev (SQLite) có thể chưa có bảng ``doctor_ratings`` (do chưa chạy
    qua migration tạo nó). Migration dùng ``IF EXISTS`` để tương thích.

Downgrade: no-op an toàn — không thể khôi phục dữ liệu đã xóa.

Revision ID: 1c2d3e4f5a6b
Revises: 1a2b3c4d5e6f
Create Date: 2026-07-12 12:30:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1c2d3e4f5a6b"
down_revision = "1a2b3c4d5e6f"
branch_labels = None
depends_on = None


ROLE_PATIENT = "patient"
PERM_RATING_READ = "rating:read"
PERM_RATING_WRITE = "rating:write"
PERM_RATING_MANAGE = "rating:manage"
PERMISSIONS_TO_DROP = (PERM_RATING_READ, PERM_RATING_WRITE, PERM_RATING_MANAGE)


def _table_exists(conn, table_name):
    """Check table có tồn tại không (DB-agnostic)."""
    bind = op.get_bind()
    dialect = bind.dialect.name if bind else ""
    if dialect == "postgresql":
        row = conn.execute(
            sa.text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_name = :name"
            ),
            {"name": table_name},
        ).first()
        return row is not None
    # SQLite / generic: thử SELECT
    try:
        conn.execute(sa.text(f"SELECT 1 FROM {table_name} LIMIT 0"))
        return True
    except Exception:
        return False


def upgrade():
    conn = op.get_bind()

    # -------------------------------------------------------------- #
    # 1) Drop bảng ``doctor_ratings`` nếu tồn tại.                  #
    # -------------------------------------------------------------- #
    if _table_exists(conn, "doctor_ratings"):
        op.drop_table("doctor_ratings")

    # -------------------------------------------------------------- #
    # 2) Drop cột ``average_rating``, ``total_ratings`` trên          #
    #    ``doctor_statistics`` (idempotent).                          #
    # -------------------------------------------------------------- #
    if _table_exists(conn, "doctor_statistics"):
        with op.batch_alter_table("doctor_statistics", schema=None) as batch_op:
            for col in ("average_rating", "total_ratings"):
                try:
                    batch_op.drop_column(col)
                except Exception:
                    # Cột chưa tồn tại -> bỏ qua (SQLite batch mode strict).
                    pass

    # -------------------------------------------------------------- #
    # 3) Drop role ``patient`` (cascade FK trước).                   #
    # -------------------------------------------------------------- #
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
    permissions = sa.table(
        "permissions",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
    )

    patient_role_id = conn.execute(
        sa.select(roles.c.id).where(roles.c.name == ROLE_PATIENT)
    ).scalar()
    if patient_role_id is not None:
        conn.execute(
            user_roles.delete().where(user_roles.c.role_id == patient_role_id)
        )
        conn.execute(
            role_permissions.delete().where(
                role_permissions.c.role_id == patient_role_id
            )
        )
        conn.execute(roles.delete().where(roles.c.id == patient_role_id))

    # -------------------------------------------------------------- #
    # 4) Drop 3 permission ``rating:*`` (cascade role_permissions).  #
    # -------------------------------------------------------------- #
    for perm_name in PERMISSIONS_TO_DROP:
        perm_id = conn.execute(
            sa.select(permissions.c.id).where(permissions.c.name == perm_name)
        ).scalar()
        if perm_id is None:
            continue
        conn.execute(
            role_permissions.delete().where(
                role_permissions.c.permission_id == perm_id
            )
        )
        conn.execute(
            permissions.delete().where(permissions.c.id == perm_id)
        )


def downgrade():
    # Refactor không thể rollback sạch: cần seed lại role + permission mapping
    # cũ + tạo lại bảng/cột đã xóa. Viết no-op an toàn kèm log cảnh báo.
    import logging

    logging.getLogger("alembic.env").warning(
        "downgrade() của 1c2d3e4f5a6b là no-op: role 'patient', 3 permission "
        "'rating:*', bảng 'doctor_ratings' và 2 cột 'average_rating'/'total_ratings' "
        "trên 'doctor_statistics' đã bị xóa. Nếu cần khôi phục, hãy seed lại thủ "
        "công và viết migration riêng."
    )
    return