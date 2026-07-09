"""Helper phân quyền dùng chung cho các service.

Quy tắc "ưu tiên admin":
  - Một user có thể mang nhiều role (vd vừa `admin` vừa `department_head`).
  - Khi có cả admin + department_head, **admin "thắng"**: được xem/sửa
    mọi bác sĩ ở mọi khoa. Logic check khoa KHÔNG chạy trong nhánh này.
  - Nếu KHÔNG có admin → mới rơi xuống nhánh department_head và bắt buộc
    bác sĩ phải thuộc khoa mà user đang làm trưởng.
  - Nếu user không có role nào trong tập được phép → 403.
"""
from __future__ import annotations

from typing import Optional

from ..errors import ForbiddenException
from .roles import Role


def is_admin(actor) -> bool:
    """True nếu actor có role admin (ưu tiên cao nhất)."""
    return bool(actor and actor.has_role(Role.ADMIN))


def is_department_head(actor) -> bool:
    """True nếu actor có role department_head."""
    return bool(actor and actor.has_role(Role.DEPARTMENT_HEAD))


def require_any(actor, *roles: str) -> None:
    """Bắt buộc actor phải có ít nhất 1 role trong `roles`, nếu không → 403."""
    if not actor or not actor.has_role(*roles):
        raise ForbiddenException("errors.forbidden")


def require_admin(actor) -> None:
    """Chỉ admin mới được phép (vd DELETE bác sĩ)."""
    if not actor or not actor.has_role(Role.ADMIN):
        raise ForbiddenException("errors.forbidden")


def resolve_doctor_scope(
    actor,
    doctor,
    department_repo,
) -> None:
    """Kiểm tra quyền xem/sửa bác sĩ với ưu tiên admin.

    Quy tắc:
      1. Không đăng nhập hoặc không có admin/department_head -> 403.
      2. Có admin -> pass ngay (xem/sửa mọi bác sĩ, KHONG check khoa).
      3. Chỉ có department_head:
         - User chưa được gán làm trưởng khoa nào -> 403
           (mã `errors.head_no_department`).
         - Doctor không thuộc khoa mình -> 403
           (mã `errors.forbidden`).
         - Ngược lại pass.

    Args:
        actor: User đang thực hiện (instance User có method `has_role`).
        doctor: Instance Doctor cần kiểm tra (đã được load).
            Truyền `None` để skip phần load — helper vẫn hoạt động đúng
            vì admin thì không cần doctor.
        department_repo: DepartmentRepository (hoặc bất kỳ object có
            method `find_by_head_doctor_id(actor_id)`).
    """
    if not actor or not actor.has_role(Role.ADMIN, Role.DEPARTMENT_HEAD):
        raise ForbiddenException("errors.forbidden")

    # Ưu tiên admin: nếu có admin thì pass ngay — KHONG check khoa.
    if actor.has_role(Role.ADMIN):
        return

    # Nhánh department_head (chắc chắn không có admin vì đã return ở trên).
    if doctor is None:
        raise ForbiddenException("errors.forbidden")

    my_dept = department_repo.find_by_head_doctor_id(actor.id)
    if my_dept is None:
        raise ForbiddenException("errors.head_no_department")

    if doctor.department_id != my_dept.id:
        raise ForbiddenException("errors.forbidden")


def resolve_list_scope(
    actor,
    department_repo,
    requested_department_id: Optional[int] = None,
) -> Optional[int]:
    """Trả về `department_id` được phép xem, hoặc `None` nếu xem toàn bộ.

    Quy tắc:
      - Có admin -> trả về `requested_department_id` nguyên xi (None = all).
      - Chỉ department_head -> ép về khoa của mình; nếu client gửi khoa
        khác thì 403.

    Args:
        actor: User đang thực hiện.
        department_repo: DepartmentRepository (có `find_by_head_doctor_id`).
        requested_department_id: filter khoa client gửi (có thể None).

    Returns:
        None = xem tất cả khoa; int = chỉ xem khoa đó.

    Raises:
        ForbiddenException: không có quyền.
    """
    require_any(actor, Role.ADMIN, Role.DEPARTMENT_HEAD)

    if actor.has_role(Role.ADMIN):
        return requested_department_id

    # Department_head (không có admin).
    my_dept = department_repo.find_by_head_doctor_id(actor.id)
    if my_dept is None:
        raise ForbiddenException("errors.head_no_department")

    if requested_department_id is not None and requested_department_id != my_dept.id:
        raise ForbiddenException("errors.forbidden")

    return my_dept.id