"""Service quản lý khoa/chuyên khoa (khu vực admin)."""
from ..common.roles import Role
from ..errors import BadRequestException, ConflictException, NotFoundException
from ..models.department import Department
from ..repositories.department_repository import DepartmentRepository
from ..repositories.role_repository import RoleRepository
from ..repositories.user_repository import UserRepository


class DepartmentService:
    def __init__(
        self, department_repository=None, user_repository=None, role_repository=None
    ):
        self.departments = department_repository or DepartmentRepository()
        self.users = user_repository or UserRepository()
        self.roles = role_repository or RoleRepository()

    def list_departments(self, page, size):
        """Danh sách khoa phân trang. Trả về (items, total)."""
        return self.departments.paginate(page, size)

    def create_department(
        self,
        code,
        name,
        description=None,
        keywords=None,
        conditions=None,
        ai_metadata=None,
        head_doctor_id=None,
    ):
        # 1. Mã khoa phải duy nhất.
        if self.departments.find_by_code(code) is not None:
            raise ConflictException("errors.department_code_exists")

        # 2. Nếu chỉ định trưởng khoa: phải tồn tại và phải đang là bác sĩ.
        head = None
        if head_doctor_id is not None:
            head = self.users.find_by_id(head_doctor_id)
            if head is None:
                raise NotFoundException("errors.head_doctor_not_found")
            if not head.has_role(Role.DOCTOR):
                raise BadRequestException("errors.head_doctor_not_doctor")

        department = Department(
            code=code,
            name=name,
            description=description,
            keywords=keywords or [],
            conditions=conditions or [],
            ai_metadata=ai_metadata or {},
            head_doctor_id=head.id if head else None,
        )
        self.departments.add(department)

        # 3. Auto-grant role department_head cho trưởng khoa (idempotent).
        if head is not None:
            self._grant_department_head(head)

        # Commit chung 1 transaction cho cả tạo khoa + cấp role.
        self.departments.commit()
        return department

    def _grant_department_head(self, user):
        role = self.roles.find_by_name(Role.DEPARTMENT_HEAD)
        if role is not None and role not in user.roles:
            user.roles.append(role)
