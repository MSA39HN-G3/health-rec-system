"""add patient:read and patient:manage permissions

Endpoints quản lý bệnh nhân trước đây gate bằng ``user:read`` / ``user:manage`` —
đây là permission dành cho admin CRUD tài khoản, không phải để quản lý hồ sơ
bệnh nhân. Hệ quả: staff (lễ tân/điều dưỡng) và doctor không có quyền xem danh
sách bệnh nhân.

Migration này:
  1. Thêm 2 permission mới: ``patient:read`` và ``patient:manage``.
  2. Gán permission mặc định theo ``DEFAULT_ROLE_PERMISSIONS`` (admin/staff/doctor)
     cho các role đã seed (idempotent).

Downgrade: xóa 2 permission + role_permissions liên kết. KHÔNG thể rollback các
quyền admin đã gán thủ công.

Revision ID: 7a8b9c0d1e2f
Revises: 6e7f8a9b0c1d
Create Date: 2026-07-12 09:45:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7a8b9c0d1e2f"
down_revision = "6e7f8a9b0c1d"
branch_labels = None
depends_on = None


# Tên permission mới (phải khớp với Permission.PATIENT_* trong app/common/roles.py).
PERM_PATIENT_READ = "patient:read"
PERM_PATIENT_MANAGE = "patient:manage"

# Mapping role -> permission mặc định khi seed (lấy từ DEFAULT_ROLE_PERMISSIONS).
DEFAULT_ROLE_PERMISSIONS = {
    "admin": [PERM_PATIENT_READ, PERM_PATIENT_MANAGE],
    "staff": [PERM_PATIENT_READ, PERM_PATIENT_MANAGE],
    "doctor": [PERM_PATIENT_READ],
    # patient: read-only không cần; chỉ cần xem hồ sơ của chính mình
    # (kiểm soát ở mức row-scope, không phải permission).
}


def upgrade():
    conn = op.get_bind()

    permissions = sa.table(
        "permissions",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
    )
    roles = sa.table(
        "roles",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
    )
    role_permissions = sa.table(
        "role_permissions",
        sa.column("role_id", sa.Integer),
        sa.column("permission_id", sa.Integer),
    )

    # 1. Tạo permission mới (idempotent).
    new_perms = [
        {
            "name": PERM_PATIENT_READ,
            "description": "Xem danh sách và chi tiết bệnh nhân",
        },
        {
            "name": PERM_PATIENT_MANAGE,
            "description": "Tạo và sửa hồ sơ bệnh nhân",
        },
    ]
    for perm in new_perms:
        existing = conn.execute(
            sa.select(permissions.c.id).where(permissions.c.name == perm["name"])
        ).scalar()
        if existing is None:
            conn.execute(permissions.insert().values(**perm))

    # 2. Gán permission mặc định cho từng role (idempotent).
    for role_name, perm_names in DEFAULT_ROLE_PERMISSIONS.items():
        role_id = conn.execute(
            sa.select(roles.c.id).where(roles.c.name == role_name)
        ).scalar()
        if role_id is None:
            # Role chưa tồn tại (vd clean DB) — bỏ qua; CLI seed-rbac sẽ lo phần còn lại.
            continue

        for perm_name in perm_names:
            perm_id = conn.execute(
                sa.select(permissions.c.id).where(permissions.c.name == perm_name)
            ).scalar()
            if perm_id is None:
                continue

            # Idempotent: chỉ insert nếu chưa có.
            existing_link = conn.execute(
                sa.select(role_permissions).where(
                    sa.and_(
                        role_permissions.c.role_id == role_id,
                        role_permissions.c.permission_id == perm_id,
                    )
                )
            ).first()
            if existing_link is None:
                conn.execute(
                    role_permissions.insert().values(
                        role_id=role_id, permission_id=perm_id
                    )
                )


def downgrade():
    conn = op.get_bind()

    permissions = sa.table(
        "permissions",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
    )
    role_permissions = sa.table(
        "role_permissions",
        sa.column("role_id", sa.Integer),
        sa.column("permission_id", sa.Integer),
    )

    for perm_name in (PERM_PATIENT_READ, PERM_PATIENT_MANAGE):
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