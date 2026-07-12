"""Hằng số role & permission + mapping mặc định để seed.

Nguồn dữ liệu thật của RBAC nằm trong DB (bảng roles, permissions, user_roles,
role_permissions). Các hằng số dưới đây chỉ để:
  - tiện dùng khi viết decorator (vd require_role(Role.ADMIN)),
  - và làm dữ liệu khởi tạo (seed) ban đầu.

Quan hệ:
  - 1 user  có nhiều role   (nhiều-nhiều).
  - 1 role  có nhiều permission (nhiều-nhiều).
  - User mới (onboard) KHÔNG có role nào; admin gán sau.

Lịch sử refactor:
  - 1a2b3c4d5e6f: bỏ role ``doctor`` + ``head_doctor_id``.
  - 1c2d3e4f5a6b: bỏ role ``patient`` + 3 permission ``rating:*`` + toàn bộ
    tính năng đánh giá bác sĩ.
"""


class Role:
    ADMIN = "admin"
    # STAFF = nhân viên bệnh viện (quản lý bác sĩ, bệnh nhân, lịch hẹn...).
    # Trước đây role `department_head` đã gộp vào `staff`, sau đó role
    # `doctor` cũng được bỏ (refactor 1a2b3c4d5e6f — staff quản lý tất cả bác
    # sĩ thông qua entity `doctors`, không còn scope theo khoa).
    STAFF = "staff"

    ALL = (ADMIN, STAFF)


class Permission:
    USER_READ = "user:read"          # xem danh sách user
    USER_MANAGE = "user:manage"      # gán/gỡ role cho user
    ROLE_MANAGE = "role:manage"      # tạo role, gán permission cho role
    RECORD_READ = "record:read"      # xem hồ sơ
    RECORD_WRITE = "record:write"    # tạo/sửa hồ sơ
    DEPARTMENT_MANAGE = "department:manage"  # quản lý khoa
    SYMPTOM_MANAGE = "symptom:manage"        # quản lý triệu chứng & ánh xạ
    PATIENT_READ = "patient:read"    # xem danh sách / chi tiết bệnh nhân
    PATIENT_MANAGE = "patient:manage"  # tạo/sửa hồ sơ bệnh nhân
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
        PATIENT_READ,
        PATIENT_MANAGE,
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
    Permission.PATIENT_READ: "Xem danh sách và chi tiết bệnh nhân",
    Permission.PATIENT_MANAGE: "Tạo và sửa hồ sơ bệnh nhân",
    Permission.APPOINTMENT_READ: "Xem danh sách và chi tiết lịch hẹn",
    Permission.APPOINTMENT_MANAGE: "Đổi trạng thái và hủy lịch hẹn",
}

# Role -> danh sách permission mặc định khi seed.
# Sau refactor 1a2b3c4d5e6f: role ``doctor`` đã bỏ.
# Sau refactor 1c2d3e4f5a6b: role ``patient`` + 3 permission ``rating:*`` đã bỏ
# (toàn bộ tính năng đánh giá bác sĩ bị xóa).
DEFAULT_ROLE_PERMISSIONS = {
    Role.ADMIN: [
        Permission.USER_READ,
        Permission.USER_MANAGE,
        Permission.ROLE_MANAGE,
        Permission.DEPARTMENT_MANAGE,
        Permission.SYMPTOM_MANAGE,
        Permission.PATIENT_READ,
        Permission.PATIENT_MANAGE,
        Permission.APPOINTMENT_READ,
        Permission.APPOINTMENT_MANAGE,
    ],
    # Staff: quản lý tất cả bác sĩ (CRUD), bệnh nhân, lịch hẹn. Không có
    # permission đặc quyền của admin (vd `user:manage`, `role:manage`).
    Role.STAFF: [
        Permission.RECORD_READ,
        Permission.RECORD_WRITE,
        Permission.DEPARTMENT_MANAGE,
        Permission.PATIENT_READ,
        Permission.PATIENT_MANAGE,
        Permission.APPOINTMENT_READ,
    ],
}