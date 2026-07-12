"""Helper phân quyền dùng chung cho các service.

Quy tắc "ưu tiên admin":
  - Một user có thể mang nhiều role (vd vừa `admin` vừa `staff`).
  - Khi có cả admin + staff, **admin "thắng"**: được xem/sửa
    mọi bác sĩ ở mọi khoa. Logic check khoa KHÔNG chạy trong nhánh này.
  - Nếu KHÔNG có admin → mới rơi xuống nhánh staff. Staff quản lý tất cả bác sĩ
    (không còn giới hạn theo khoa như trước — khái niệm "trưởng khoa" đã bỏ ở
    refactor 1a2b3c4d5e6f). Nếu FE muốn giới hạn, FE tự truyền filter
    `department_id` xuống BE.
  - Nếu user không có role nào trong tập được phép → 403.
"""
from __future__ import annotations

from typing import Optional

from ..errors import ForbiddenException
from .roles import Role


def is_admin(actor) -> bool:
    """True nếu actor có role admin (ưu tiên cao nhất)."""
    return bool(actor and actor.has_role(Role.ADMIN))


def is_staff(actor) -> bool:
    """True nếu actor có role staff (quản lý tất cả bác sĩ, không còn scope khoa)."""
    return bool(actor and actor.has_role(Role.STAFF))


def require_any(actor, *roles: str) -> None:
    """Bắt buộc actor phải có ít nhất 1 role trong `roles`, nếu không → 403."""
    if not actor or not actor.has_role(*roles):
        raise ForbiddenException("errors.forbidden")


def require_admin(actor) -> None:
    """Chỉ admin mới được phép (vd DELETE bác sĩ)."""
    if not actor or not actor.has_role(Role.ADMIN):
        raise ForbiddenException("errors.forbidden")


def resolve_doctor_scope(actor, doctor) -> None:
    """Kiểm tra quyền xem/sửa bác sĩ với ưu tiên admin.

    Quy tắc (sau refactor 1a2b3c4d5e6f — staff quản lý tất cả bác sĩ):
      1. Không đăng nhập hoặc không có admin/staff -> 403.
      2. Có admin hoặc staff -> pass (không check khoa).

    Args:
        actor: User đang thực hiện (instance User có method `has_role`).
        doctor: Instance Doctor cần kiểm tra. Không còn dùng để filter, nhưng
            giữ tham số để tương thích với call-site cũ (ignored).
    """
    if not actor or not actor.has_role(Role.ADMIN, Role.STAFF):
        raise ForbiddenException("errors.forbidden")
    # Có admin hoặc staff -> pass luôn, không còn filter theo khoa.
    _ = doctor  # giữ tham số cho tương thích call-site cũ


def resolve_list_scope(
    actor,
    requested_department_id: Optional[int] = None,
) -> Optional[int]:
    """Trả về `department_id` được phép xem, hoặc `None` nếu xem toàn bộ.

    Quy tắc (sau refactor 1a2b3c4d5e6f):
      - Có admin/staff -> trả về `requested_department_id` nguyên xi
        (None = all). FE tự chịu trách nhiệm filter theo khoa.

    Args:
        actor: User đang thực hiện.
        requested_department_id: filter khoa client gửi (có thể None).

    Returns:
        None = xem tất cả khoa; int = chỉ xem khoa đó.
    """
    require_any(actor, Role.ADMIN, Role.STAFF)
    return requested_department_id