"""Hằng số role & permission + mapping mặc định để seed.

Nguồn dữ liệu thật của RBAC nằm trong DB (bảng roles, permissions, user_roles,
role_permissions). Các hằng số dưới đây chỉ để:
  - tiện dùng khi viết decorator (vd require_role(Role.ADMIN)),
  - và làm dữ liệu khởi tạo (seed) ban đầu.

Quan hệ:
  - 1 user  có nhiều role   (nhiều-nhiều).
  - 1 role  có nhiều permission (nhiều-nhiều).
  - User mới (onboard) KHÔNG có role nào; admin gán sau.
"""


class Role:
    ADMIN = "admin"
    DEPARTMENT_HEAD = "department_head"
    DOCTOR = "doctor"

    ALL = (ADMIN, DEPARTMENT_HEAD, DOCTOR)


class Permission:
    USER_READ = "user:read"          # xem danh sách user
    USER_MANAGE = "user:manage"      # gán/gỡ role cho user
    ROLE_MANAGE = "role:manage"      # tạo role, gán permission cho role
    RECORD_READ = "record:read"      # xem hồ sơ
    RECORD_WRITE = "record:write"    # tạo/sửa hồ sơ
    DEPARTMENT_MANAGE = "department:manage"  # quản lý khoa

    ALL = (
        USER_READ,
        USER_MANAGE,
        ROLE_MANAGE,
        RECORD_READ,
        RECORD_WRITE,
        DEPARTMENT_MANAGE,
    )


# Mô tả ngắn cho từng permission (dùng khi seed).
PERMISSION_DESCRIPTIONS = {
    Permission.USER_READ: "Xem danh sách người dùng",
    Permission.USER_MANAGE: "Quản lý người dùng (gán/gỡ role)",
    Permission.ROLE_MANAGE: "Quản lý role và permission",
    Permission.RECORD_READ: "Xem hồ sơ sức khỏe",
    Permission.RECORD_WRITE: "Tạo/sửa hồ sơ sức khỏe",
    Permission.DEPARTMENT_MANAGE: "Quản lý khoa",
}

# Role -> danh sách permission mặc định khi seed.
DEFAULT_ROLE_PERMISSIONS = {
    Role.ADMIN: [
        Permission.USER_READ,
        Permission.USER_MANAGE,
        Permission.ROLE_MANAGE,
        Permission.DEPARTMENT_MANAGE,
    ],
    Role.DEPARTMENT_HEAD: [
        Permission.RECORD_READ,
        Permission.RECORD_WRITE,
        Permission.DEPARTMENT_MANAGE,
    ],
    Role.DOCTOR: [
        Permission.RECORD_READ,
        Permission.RECORD_WRITE,
    ],
}
