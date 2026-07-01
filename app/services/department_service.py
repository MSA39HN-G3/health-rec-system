"""Service quản lý khoa/chuyên khoa (khu vực admin)."""
from sqlalchemy.exc import IntegrityError

from ..common.roles import Role
from ..errors import BadRequestException, ConflictException, NotFoundException
from ..models.department import Department
from ..repositories.department_repository import DepartmentRepository
from ..repositories.role_repository import RoleRepository
from ..repositories.user_repository import UserRepository

# Tiền tố mã chuyên khoa (vd "CK-001") và số lần thử lại khi đụng độ mã do tạo
# đồng thời (unique violation) trước khi bỏ cuộc.
_CODE_PREFIX = "CK-"
_MAX_CODE_RETRIES = 5

# Sentinel phân biệt "không truyền field" (giữ nguyên) với "truyền null" (xóa) khi
# cập nhật từng phần (PATCH).
_UNSET = object()


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

    def get_stats(self):
        """Thống kê số lượng khoa: tổng, đang hoạt động, tạm dừng."""
        total, active, inactive = self.departments.count_by_status()
        return {"total": total, "active": active, "inactive": inactive}

    def create_department(
        self,
        name,
        location=None,
        description=None,
        keywords=None,
        conditions=None,
        ai_metadata=None,
        head_doctor_id=None,
    ):
        # 1. Nếu chỉ định trưởng khoa: phải tồn tại và phải đang là bác sĩ.
        head = None
        if head_doctor_id is not None:
            head = self.users.find_by_id(head_doctor_id)
            if head is None:
                raise NotFoundException("errors.head_doctor_not_found")
            if not head.has_role(Role.DOCTOR):
                raise BadRequestException("errors.head_doctor_not_doctor")

        # 2. Trạng thái hoạt động = true KHI VÀ CHỈ KHI có trưởng khoa.
        is_active = head is not None

        # 3. Sinh mã "CK-NNN" duy nhất do hệ thống cấp. Thử lại nếu đụng độ unique
        #    do hai request tạo khoa cùng lúc cùng tính ra một số thứ tự.
        for _ in range(_MAX_CODE_RETRIES):
            department = Department(
                code=self._next_code(),
                name=name,
                location=location,
                description=description,
                keywords=keywords or [],
                conditions=conditions or [],
                ai_metadata=ai_metadata or {},
                head_doctor_id=head.id if head else None,
                is_active=is_active,
            )
            self.departments.add(department)

            # Auto-grant role department_head cho trưởng khoa (idempotent).
            if head is not None:
                self._grant_department_head(head)

            try:
                # Commit chung 1 transaction cho cả tạo khoa + cấp role.
                self.departments.commit()
                return department
            except IntegrityError:
                self.departments.rollback()

        # Hết số lần thử mà vẫn đụng độ -> coi như xung đột mã khoa.
        raise ConflictException("errors.department_code_exists")

    def update_department(
        self,
        department_id,
        *,
        name=_UNSET,
        location=_UNSET,
        avatar_url=_UNSET,
        description=_UNSET,
        keywords=_UNSET,
        conditions=_UNSET,
        techniques=_UNSET,
        ai_metadata=_UNSET,
        head_doctor_id=_UNSET,
    ):
        """Cập nhật từng phần một khoa. Chỉ các field được truyền mới thay đổi.

        Mã khoa (`code`) là cố định, không cho sửa. Khi đổi trưởng khoa thì
        `is_active` được tính lại theo quy tắc iff (true ⇔ có trưởng khoa).
        """
        department = self.departments.find_by_id(department_id)
        if department is None:
            raise NotFoundException("errors.department_not_found")

        # Đổi trưởng khoa -> kéo theo cập nhật is_active (true ⇔ có trưởng khoa).
        if head_doctor_id is not _UNSET:
            head = None
            if head_doctor_id is not None:
                head = self.users.find_by_id(head_doctor_id)
                if head is None:
                    raise NotFoundException("errors.head_doctor_not_found")
                if not head.has_role(Role.DOCTOR):
                    raise BadRequestException("errors.head_doctor_not_doctor")
            department.head_doctor_id = head.id if head else None
            department.is_active = head is not None
            if head is not None:
                self._grant_department_head(head)

        if name is not _UNSET:
            department.name = name
        if location is not _UNSET:
            department.location = location
        if avatar_url is not _UNSET:
            department.avatar_url = avatar_url
        if description is not _UNSET:
            department.description = description
        if keywords is not _UNSET:
            department.keywords = keywords
        if conditions is not _UNSET:
            department.conditions = conditions
        if techniques is not _UNSET:
            department.techniques = techniques
        if ai_metadata is not _UNSET:
            department.ai_metadata = ai_metadata

        self.departments.commit()
        return department

    def _next_code(self):
        """Mã chuyên khoa kế tiếp dạng `CK-NNN` (NNN >= 001, zero-pad 3 chữ số)."""
        return f"{_CODE_PREFIX}{self.departments.max_code_number(_CODE_PREFIX) + 1:03d}"

    def _grant_department_head(self, user):
        role = self.roles.find_by_name(Role.DEPARTMENT_HEAD)
        if role is not None and role not in user.roles:
            user.roles.append(role)
