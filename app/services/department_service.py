"""Service quản lý khoa/chuyên khoa (khu vực admin)."""
import logging

from sqlalchemy.exc import IntegrityError

from ..common.roles import Role
from ..errors import BadRequestException, ConflictException, NotFoundException
from ..models.department import Department
from ..repositories.department_repository import DepartmentRepository
from ..repositories.role_repository import RoleRepository
from ..repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

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
        is_active=False,
    ):
        # 1. Nếu chỉ định trưởng khoa: phải tồn tại và phải đang là bác sĩ.
        head = None
        if head_doctor_id is not None:
            head = self.users.find_by_id(head_doctor_id)
            if head is None:
                raise NotFoundException("errors.head_doctor_not_found")
            if not head.has_role(Role.DOCTOR):
                raise BadRequestException("errors.head_doctor_not_doctor")

        # 2. Nghiệp vụ: bật khoa (`is_active=True`) chỉ hợp lệ khi đã chọn được
        #    một trưởng khoa hợp lệ. Đây là ràng buộc giữa 2 field nên được kiểm
        #    tra ở service (raise 400), không phải ở tầng validation 422.
        if is_active and head is None:
            raise BadRequestException("errors.head_required_when_active")

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
        avatar_object_key=_UNSET,
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

        `avatar_object_key` được ưu tiên hơn `avatar_url`: khi set object_key
        thì cũng xoá cache URL cũ để buộc BE sinh lại presigned GET lần kế.
        Gửi null cho cả hai field đều xoá ảnh.
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
        if avatar_object_key is not _UNSET:
            # Snapshot key cũ TRƯỚC khi gán — dùng để xóa object trên R2
            # sau khi commit DB thành công (xem `self._cleanup_old_avatar`).
            old_object_key = department.avatar_object_key
            new_object_key = avatar_object_key

            department.avatar_object_key = new_object_key
            # Khi gán object_key mới hoặc xoá (None) thì cache URL cũ không
            # còn hợp lệ -> xoá để to_dict() tự derive lại presigned GET.
            department.avatar_url = None
        else:
            old_object_key = None
            new_object_key = None
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
        # Cleanup R2 chạy SAU commit: nếu commit fail thì DB vẫn giữ key cũ,
        # R2 cũng còn file cũ -> dữ liệu nhất quán. Nếu commit OK mà xóa R2
        # lỗi thì chỉ tốn storage (orphan), không ảnh hưởng nghiệp vụ.
        self._cleanup_old_avatar(old_object_key, new_object_key)
        return department

    def _cleanup_old_avatar(self, old_key, new_key):
        """Xóa object avatar cũ trên R2 sau khi DB đã được commit thành công.

        An toàn với:
          - PATCH đổi sang key mới (`old_key != new_key`, cả 2 khác None).
          - PATCH xoá avatar (`new_key is None`, `old_key` còn giá trị).
          - PATCH set cùng key hiện tại (idempotent, không xóa).
        Lỗi R2 chỉ log warning — không raise, không rollback.
        """
        if not old_key or old_key == new_key:
            return
        # Import trong hàm để tránh import vòng (storage -> extensions).
        from botocore.exceptions import BotoCoreError, ClientError

        from .storage import delete_object

        try:
            delete_object(old_key)
        except (BotoCoreError, ClientError) as exc:
            logger.warning(
                "Failed to delete old department avatar from R2: %s (key=%s)",
                exc,
                old_key,
            )

    def _next_code(self):
        """Mã chuyên khoa kế tiếp dạng `CK-NNN` (NNN >= 001, zero-pad 3 chữ số)."""
        return f"{_CODE_PREFIX}{self.departments.max_code_number(_CODE_PREFIX) + 1:03d}"

    def _grant_department_head(self, user):
        role = self.roles.find_by_name(Role.DEPARTMENT_HEAD)
        if role is not None and role not in user.roles:
            user.roles.append(role)
