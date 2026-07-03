"""Service quản lý danh sách bác sĩ (read-only cho API lấy danh sách).

Quy tắc phân quyền:
  - ADMIN (role `admin`)            -> xem toàn bộ bác sĩ mọi khoa.
  - DEPARTMENT_HEAD (role đó)       -> chỉ xem bác sĩ thuộc khoa mà user
                                       đang làm trưởng (Department.head_doctor_id
                                       == current_user.id).
                                       Nếu chưa được gán làm trưởng khoa nào
                                       -> 403, vì không xác định được phạm vi.
"""
from ..common.roles import Role
from ..errors import ForbiddenException
from ..repositories.department_repository import DepartmentRepository
from ..repositories.doctor_repository import DoctorRepository
from ..repositories.role_repository import RoleRepository


class DoctorService:
    def __init__(
        self,
        doctor_repository=None,
        department_repository=None,
        role_repository=None,
    ):
        self.doctors = doctor_repository or DoctorRepository()
        self.departments = department_repository or DepartmentRepository()
        self.roles = role_repository or RoleRepository()

    def list_doctors(self, actor, page, size, department_id=None):
        """Danh sách bác sĩ có phân trang, áp dụng phân quyền theo `actor`.

        `actor` là User đang đăng nhập (g.current_user). Kết quả giới hạn theo:
          - admin: tất cả khoa (trừ khi client truyền `department_id` thì
            lọc thêm theo khoa đó như một filter tiện dụng).
          - department_head: khoa mà actor làm trưởng. Nếu client truyền
            `department_id` khác khoa của actor -> 403 (vượt quyền).

        Trả về (items, total, scope) với `scope` là dict mô tả phạm vi áp dụng
        để client hiển thị ("all departments" | "department: <id>").
        """
        if not actor or not actor.has_role(Role.ADMIN, Role.DEPARTMENT_HEAD):
            raise ForbiddenException("errors.forbidden")

        if actor.has_role(Role.ADMIN):
            # Admin được phép truyền department_id để lọc thuận tiện; bỏ trống = all.
            items, total = self.doctors.paginate(
                page, size, department_id=department_id
            )
            return items, total, _scope_admin(department_id)

        # Nhánh department_head: xác định "khoa của tôi".
        my_department = self.departments.find_by_head_doctor_id(actor.id)
        if my_department is None:
            raise ForbiddenException("errors.head_no_department")

        if department_id is not None and department_id != my_department.id:
            raise ForbiddenException("errors.forbidden")

        items, total = self.doctors.paginate(
            page, size, department_id=my_department.id
        )
        return items, total, _scope_department(my_department)


def _scope_admin(department_id):
    if department_id is None:
        return {"type": "all", "department_id": None, "label": "Tất cả khoa"}
    return {
        "type": "department",
        "department_id": department_id,
        "label": f"Khoa #{department_id}",
    }


def _scope_department(department):
    return {
        "type": "department",
        "department_id": department.id,
        "label": department.name,
    }
