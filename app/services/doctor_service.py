"""Service quản lý bác sĩ - CRUD và các thao tác nghiệp vụ.

Quy tắc phân quyền (sau refactor 1a2b3c4d5e6f):
    - ADMIN (role `admin`) -> toàn quyền CRUD bác sĩ.
    - STAFF (role `staff`) -> quản lý tất cả bác sĩ (không còn scope theo
      khoa — khái niệm "trưởng khoa" đã bỏ, staff quản lý tất cả). Nếu FE
      muốn giới hạn theo khoa, FE tự truyền filter `department_id` xuống BE.

Luồng xử lý avatar trên R2:
  - Khi PATCH `avatar_object_key` đổi sang key mới / set về `null`, BE tự xóa
    object cũ trên R2 ngay sau khi commit DB. Lỗi R2 chỉ log warning — không
    rollback nghiệp vụ.
"""
import logging

from ..common.roles import Role
from ..common.scope import (
    require_admin,
    require_any,
    resolve_doctor_scope,
    resolve_list_scope,
)
from ..errors import ForbiddenException, NotFoundException, ValidationException
from ..models.doctor import Doctor
from ..repositories.department_repository import DepartmentRepository
from ..repositories.doctor_repository import DoctorRepository
from ..repositories.doctor_statistics_repository import DoctorStatisticsRepository
from ..repositories.role_repository import RoleRepository

logger = logging.getLogger(__name__)


class DoctorService:
    def __init__(
        self,
        doctor_repository=None,
        department_repository=None,
        role_repository=None,
        statistics_repository=None,
    ):
        self.doctors = doctor_repository or DoctorRepository()
        self._department_repo = department_repository
        self.roles = role_repository or RoleRepository()
        self.statistics = statistics_repository or DoctorStatisticsRepository()

    @property
    def departments(self):
        """Lazy-init DepartmentRepository để tránh tạo ngoài app context.

        Vẫn còn dùng cho các method nghiệp vụ (vd validate `department_id` khi
        tạo bác sĩ), nhưng `resolve_doctor_scope` không còn dùng repo này
        nữa vì scope đã được bỏ.
        """
        if self._department_repo is None:
            self._department_repo = DepartmentRepository()
        return self._department_repo

    # === Phân quyền ===
    def _check_list_permission(self, actor):
        """Kiểm tra quyền xem danh sách bác sĩ."""
        require_any(actor, Role.ADMIN, Role.STAFF)

    def _check_create_permission(self, actor):
        """Kiểm tra quyền tạo bác sĩ."""
        require_any(actor, Role.ADMIN, Role.STAFF)

    def _check_update_permission(self, actor, doctor):
        """Kiểm tra quyền sửa bác sĩ (ưu tiên admin)."""
        # Sau refactor 1a2b3c4d5e6f: staff cũng pass (không còn filter khoa).
        resolve_doctor_scope(actor, doctor)

    def _check_delete_permission(self, actor):
        """Chỉ admin được xóa bác sĩ."""
        require_admin(actor)

    def _check_read_permission(self, actor, doctor):
        """Kiểm tra quyền đọc thông tin bác sĩ (ưu tiên admin)."""
        # Sau refactor 1a2b3c4d5e6f: staff cũng pass (không còn filter khoa).
        resolve_doctor_scope(actor, doctor)

    # === CRUD Operations ===

    def create_doctor(self, actor, data):
        """Tạo mới bác sĩ.

        Args:
            actor: User đang thực hiện
            data: Dict chứa thông tin bác sĩ

        Returns:
            Doctor: Bác sĩ đã tạo
        """
        self._check_create_permission(actor)

        # Validate department exists
        department_id = data.get("department_id")
        department = self.departments.find_by_id(department_id)
        if not department:
            raise ValidationException(
                message_key="errors.department_not_found",
                details={"department_id": "not_found"},
            )

        # Check license number uniqueness if provided
        license_number = data.get("license_number")
        if license_number:
            existing = self.doctors.find_by_license_number(license_number)
            if existing:
                raise ValidationException(
                    message_key="errors.doctor_duplicate_license",
                    details={"license_number": "duplicate"},
                )

        # Check email uniqueness if provided
        email = data.get("email")
        if email:
            existing = self.doctors.find_by_email(email)
            if existing:
                raise ValidationException(
                    message_key="errors.doctor_duplicate_email",
                    details={"email": "duplicate"},
                )

        # Create doctor
        doctor = Doctor(
            full_name=data["full_name"],
            department_id=department_id,
            title=data.get("title"),
            # Phần 1: Thông tin cá nhân
            phone=data.get("phone"),
            email=data.get("email"),
            avatar_object_key=data.get("avatar_object_key"),
            date_of_birth=data.get("date_of_birth"),
            gender=data.get("gender"),
            address=data.get("address"),
            # Phần 2: Thông tin chuyên môn
            license_number=license_number,
            license_issue_date=data.get("license_issue_date"),
            license_expiry_date=data.get("license_expiry_date"),
            specialization=data.get("specialization"),
            sub_specializations=data.get("sub_specializations", []),
            education=data.get("education", []),
            experience_years=data.get("experience_years"),
            training_institutions=data.get("training_institutions", []),
            # Phần 5: Thông tin hành chính
            employment_type=data.get("employment_type"),
            hire_date=data.get("hire_date"),
            contract_end_date=data.get("contract_end_date"),
            is_accepting_new_patients=data.get("is_accepting_new_patients", True),
            is_active=True,
        )

        doctor = self.doctors.add(doctor)
        self.doctors.commit()

        # Create statistics record for new doctor
        self.statistics.find_or_create(doctor.id)

        return doctor

    def get_doctor(self, actor, doctor_id):
        """Lấy thông tin chi tiết bác sĩ.

        Args:
            actor: User đang thực hiện
            doctor_id: ID của bác sĩ

        Returns:
            Doctor: Bác sĩ
        """
        doctor = self.doctors.find_by_id(doctor_id)
        if not doctor:
            raise NotFoundException("errors.doctor_not_found")

        self._check_read_permission(actor, doctor)
        return doctor

    def update_doctor(self, actor, doctor_id, data):
        """Cập nhật thông tin bác sĩ. Tự xóa avatar cũ trên R2 khi `avatar_object_key` đổi / xoá.

        Args:
            actor: User đang thực hiện
            doctor_id: ID của bác sĩ
            data: Dict chứa thông tin cập nhật

        Returns:
            Doctor: Bác sĩ đã cập nhật
        """
        doctor = self.doctors.find_by_id(doctor_id)
        if not doctor:
            raise NotFoundException("errors.doctor_not_found")

        self._check_update_permission(actor, doctor)

        # Check license number uniqueness if changing
        new_license = data.get("license_number")
        if new_license and new_license != doctor.license_number:
            existing = self.doctors.find_by_license_number(new_license)
            if existing and existing.id != doctor_id:
                raise ValidationException(
                    message_key="errors.doctor_duplicate_license",
                    details={"license_number": "duplicate"},
                )

        # Check email uniqueness if changing
        new_email = data.get("email")
        if new_email and new_email != doctor.email:
            existing = self.doctors.find_by_email(new_email)
            if existing and existing.id != doctor_id:
                raise ValidationException(
                    message_key="errors.doctor_duplicate_email",
                    details={"email": "duplicate"},
                )

        # Validate department if changing
        if "department_id" in data:
            dept = self.departments.find_by_id(data["department_id"])
            if not dept:
                raise ValidationException(
                    message_key="errors.department_not_found",
                    details={"department_id": "not_found"},
                )

        # Snapshot avatar cũ trước khi gán (nếu có trong payload).
        old_avatar_key = doctor.avatar_object_key
        new_avatar_key = data.get("avatar_object_key", old_avatar_key)

        # Update fields
        updatable_fields = [
            # Core
            "full_name", "department_id", "title", "is_active",
            # Phần 1: Thông tin cá nhân
            "phone", "email", "avatar_object_key", "date_of_birth", "gender", "address",
            # Phần 2: Thông tin chuyên môn
            "license_number", "license_issue_date", "license_expiry_date",
            "specialization", "sub_specializations", "education",
            "experience_years", "training_institutions",
            # Phần 5: Thông tin hành chính
            "employment_type", "hire_date", "contract_end_date", "is_accepting_new_patients",
        ]

        for field in updatable_fields:
            if field in data:
                setattr(doctor, field, data[field])

        # Khi gán avatar_object_key mới hoặc xoá (None) thì cache URL cũ
        # không còn hợp lệ -> xoá để to_dict() tự derive lại presigned GET.
        if "avatar_object_key" in data and data["avatar_object_key"] != old_avatar_key:
            doctor.avatar_url = None

        result = self.doctors.update(doctor)
        # Cleanup R2 chạy SAU commit. Lỗi R2 không rollback DB.
        self._cleanup_old_avatar(old_avatar_key, new_avatar_key)
        return result

    def _cleanup_old_avatar(self, old_key, new_key):
        """Xóa object avatar cũ trên R2 sau khi DB đã commit thành công.

        An toàn với:
          - PATCH đổi sang key mới (`old_key != new_key`, cả 2 khác None).
          - PATCH xoá avatar (`new_key is None`, `old_key` còn giá trị).
          - PATCH set cùng key hiện tại (idempotent, không xóa).
        Lỗi R2 chỉ log warning — không raise, không rollback.
        """
        if not old_key or old_key == new_key:
            return
        from botocore.exceptions import BotoCoreError, ClientError

        from .storage import delete_object

        try:
            delete_object(old_key)
        except (BotoCoreError, ClientError) as exc:
            logger.warning(
                "Failed to delete old doctor avatar from R2: %s (key=%s)",
                exc,
                old_key,
            )

    def delete_doctor(self, actor, doctor_id):
        """Xóa bác sĩ (soft delete). Tự xóa avatar trên R2 (best-effort) sau khi commit.

        Args:
            actor: User đang thực hiện
            doctor_id: ID của bác sĩ
        """
        doctor = self.doctors.find_by_id(doctor_id)
        if not doctor:
            raise NotFoundException("errors.doctor_not_found")

        self._check_delete_permission(actor)

        # Snapshot avatar trước khi xoá.
        old_avatar_key = doctor.avatar_object_key
        self.doctors.delete(doctor)
        # Cleanup R2 chạy SAU commit.
        self._cleanup_old_avatar(old_avatar_key, None)

    # === List & Search ===

    def list_doctors(self, actor, page, size, department_id=None):
        """Danh sách bác sĩ có phân trang, áp dụng phân quyền theo `actor`.

        Quy tắc "ưu tiên admin":
          - admin → xem mọi khoa, tôn trọng filter `department_id`.
          - department_head → bị ép về khoa của mình; gửi filter khác → 403.
          - admin + department_head → rơi nhánh admin (xem mọi khoa).
        """
        self._check_list_permission(actor)

        scoped_department_id = resolve_list_scope(
            actor, department_id
        )

        items, total = self.doctors.paginate(
            page, size, department_id=scoped_department_id
        )

        if scoped_department_id is None:
            return items, total, _scope_admin(None)

        # Có filter khoa: admin thì label theo id (không cần DB lookup),
        # department_head thì label theo tên khoa của user.
        if actor.has_role(Role.ADMIN):
            return items, total, _scope_admin(scoped_department_id)
        return items, total, _scope_department(
            self.departments.find_by_id(scoped_department_id)
        )

    def search_doctors(self, actor, keyword, page, size, department_id=None):
        """Tìm kiếm bác sĩ theo từ khóa."""
        self._check_list_permission(actor)

        scoped_department_id = resolve_list_scope(
            actor, department_id
        )

        items, total = self.doctors.search(
            keyword, page, size, department_id=scoped_department_id
        )
        return items, total

    # === Utility Methods ===

    def get_expiring_licenses(self, actor, days=30):
        """Lấy danh sách bác sĩ có giấy phép sắp hết hạn (chỉ admin)."""
        require_admin(actor)
        return self.doctors.find_expiring_licenses(days)

    def get_doctor_statistics(self, actor, doctor_id):
        """Lấy thống kê của một bác sĩ."""
        doctor = self.doctors.find_by_id(doctor_id)
        if not doctor:
            raise NotFoundException("errors.not_found")
        self._check_read_permission(actor, doctor)
        return self.statistics.find_or_create(doctor_id)


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
