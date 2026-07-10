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
    PATIENT = "patient"
    STAFF = "staff"  # nhân viên (lễ tân, điều dưỡng, ...) — tạo đánh giá hộ BN

    ALL = (ADMIN, DEPARTMENT_HEAD, DOCTOR, PATIENT, STAFF)


class Permission:
    USER_READ = "user:read"          # xem danh sách user
    USER_MANAGE = "user:manage"      # gán/gỡ role cho user
    ROLE_MANAGE = "role:manage"      # tạo role, gán permission cho role
    RECORD_READ = "record:read"      # xem hồ sơ
    RECORD_WRITE = "record:write"    # tạo/sửa hồ sơ
    DEPARTMENT_MANAGE = "department:manage"  # quản lý khoa
    SYMPTOM_MANAGE = "symptom:manage"        # quản lý triệu chứng & ánh xạ
    RATING_READ = "rating:read"       # xem đánh giá
    RATING_WRITE = "rating:write"     # tạo/sửa đánh giá
    RATING_MANAGE = "rating:manage"   # xóa đánh giá (admin)
    APPOINTMENT_READ = "appointment:read"      # xem danh sách/chi tiết lịch hẹn
    APPOINTMENT_MANAGE = "appointment:manage"  # đổi trạng thái, hủy lịch hẹn

    ALL = (
        USER_READ,
        USER_MANAGE,
        ROLE_MANAGE,
        RECORD_READ,
        RECORD_WRITE,
        DEPARTMENT_MANAGE,
        SYMPTOM_MANAGE,
        RATING_READ,
        RATING_WRITE,
        RATING_MANAGE,
        APPOINTMENT_READ,
        APPOINTMENT_MANAGE,
    )


# Mô tả ngắn cho từng permission (dùng khi seed).
PERMISSION_DESCRIPTIONS = {
    Permission.USER_READ: "Xem danh sách người dùng",
    Permission.USER_MANAGE: "Quản lý người dùng (gán/gỡ role)",
    Permission.ROLE_MANAGE: "Quản lý role và permission",
    Permission.RECORD_READ: "Xem hồ sơ sức khỏe",
    Permission.RECORD_WRITE: "Tạo/sửa hồ sơ sức khỏe",
    Permission.DEPARTMENT_MANAGE: "Quản lý khoa",
    Permission.SYMPTOM_MANAGE: "Quản lý triệu chứng và ánh xạ chuyên khoa",
    Permission.RATING_READ: "Xem đánh giá bác sĩ",
    Permission.RATING_WRITE: "Tạo và sửa đánh giá bác sĩ",
    Permission.RATING_MANAGE: "Quản lý (xóa) đánh giá bác sĩ",
    Permission.APPOINTMENT_READ: "Xem danh sách và chi tiết lịch hẹn",
    Permission.APPOINTMENT_MANAGE: "Đổi trạng thái và hủy lịch hẹn",
}

# Role -> danh sách permission mặc định khi seed.
DEFAULT_ROLE_PERMISSIONS = {
    Role.ADMIN: [
        Permission.USER_READ,
        Permission.USER_MANAGE,
        Permission.ROLE_MANAGE,
        Permission.DEPARTMENT_MANAGE,
        Permission.SYMPTOM_MANAGE,
        Permission.RATING_READ,
        Permission.RATING_WRITE,
        Permission.RATING_MANAGE,
        Permission.APPOINTMENT_READ,
        Permission.APPOINTMENT_MANAGE,
    ],
    Role.DEPARTMENT_HEAD: [
        Permission.RECORD_READ,
        Permission.RECORD_WRITE,
        Permission.DEPARTMENT_MANAGE,
        Permission.RATING_READ,
        Permission.APPOINTMENT_READ,
    ],
    Role.DOCTOR: [
        Permission.RECORD_READ,
        Permission.RECORD_WRITE,
        Permission.RATING_READ,
    ],
    Role.PATIENT: [
        Permission.RATING_READ,
        Permission.RATING_WRITE,
    ],
}
