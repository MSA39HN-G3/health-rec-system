content = '''"""Service quản lý tài liệu bác sĩ.

Quy tắc phân quyền (sau refactor 1a2b3c4d5e6f, ưu tiên admin):
  - ADMIN                       -> quản lý tài liệu bác sĩ ở mọi khoa.
  - STAFF                       -> quản lý tất cả bác sĩ (không còn scope khoa).
  - admin + staff               -> admin thắng (xem/sửa mọi khoa).

Luồng xử lý object_key trên R2:
  - Khi PATCH `object_key` đổi sang key mới / set về `null`, BE tự xóa object
    cũ trên R2 ngay sau khi commit DB thành công. Lỗi R2 chỉ log warning —
    không rollback nghiệp vụ.
  - Khi DELETE tài liệu, object_key cũng bị xóa khỏi R2 (best-effort).
"""
import logging

from ..common.roles import Role
from ..common.scope import resolve_doctor_scope, require_admin
from ..errors import ForbiddenException, NotFoundException, ValidationException
from ..models.doctor_document import DoctorDocument, DOCUMENT_TYPES
from ..repositories.department_repository import DepartmentRepository
from ..repositories.doctor_document_repository import DoctorDocumentRepository
from ..repositories.doctor_repository import DoctorRepository

logger = logging.getLogger(__name__)


class DoctorDocumentService:
    def __init__(
        self,
        document_repository=None,
        doctor_repository=None,
        department_repository=None,
    ):
        self.documents = document_repository or DoctorDocumentRepository()
        self.doctors = doctor_repository or DoctorRepository()
        # `department_repository` vẫn nhận để tương thích call-site cũ nhưng
        # không còn được dùng trong scope check sau refactor 1a2b3c4d5e6f.
        self._department_repo = department_repository

    @property
    def departments(self):
        """Lazy-init DepartmentRepository để tránh tạo ngoài app context."""
        if self._department_repo is None:
            self._department_repo = DepartmentRepository()
        return self._department_repo

    def _check_permission(self, actor, doctor_id):
        """Kiểm tra quyền truy cập tài liệu của một bác sĩ (ưu tiên admin).

        Quy tắc (sau refactor 1a2b3c4d5e6f — staff quản lý tất cả bác sĩ):
          - admin                       -> pass ngay (mọi khoa, không cần load doctor).
          - staff                       -> pass (quản lý tất cả bác sĩ).
          - admin + staff               -> rơi nhánh admin (pass ngay).
          - role khác                   -> 403.
          - doctor_id không tồn tại     -> 404.
        """
        # Admin không cần load doctor (ưu tiên admin).
        # Staff mới cần load để kiểm tra doctor tồn tại (chỉ check existence,
        # không còn filter khoa).
        doctor = None
        if actor is None or not actor.has_role(Role.ADMIN):
            doctor = self.doctors.find_by_id(doctor_id)
            if doctor is None:
                raise NotFoundException("errors.not_found")

        # Sau refactor: staff pass luôn, không còn check khoa.
        resolve_doctor_scope(actor, doctor)

    def _check_admin_only(self, actor):
        """Chỉ admin được thực hiện (vd verify tài liệu)."""
        require_admin(actor)

    def _cleanup_old_object(self, old_key, new_key=None):
        """Xóa object trên R2 sau khi DB đã commit thành công.

        An toàn với:
          - PATCH đổi sang key mới (`old_key != new_key`, cả 2 khác None).
          - PATCH xoá object_key (`new_key is None`, `old_key` còn giá trị).
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
                "Failed to delete old doctor document from R2: %s (key=%s)",
                exc,
                old_key,
            )

    def list_documents(self, actor, doctor_id, document_type=None):
        """Lấy danh sách tài liệu của bác sĩ."""
        doctor = self.doctors.find_by_id(doctor_id)
        if not doctor:
            raise NotFoundException("errors.not_found")

        self._check_permission(actor, doctor_id)

        if document_type and document_type not in DOCUMENT_TYPES:
            raise ValidationException({"document_type": "invalid_choice"})

        return self.documents.find_by_doctor_id(doctor_id, document_type)

    def get_document(self, actor, document_id):
        """Lấy chi tiết một tài liệu."""
        doc = self.documents.find_by_id(document_id)
        if not doc:
            raise NotFoundException("errors.not_found")

        self._check_permission(actor, doc.doctor_id)
        return doc

    def create_document(self, actor, doctor_id, data):
        """Tạo mới tài liệu cho bác sĩ.

        Quy tắc `is_verified` mặc định:
          - admin / staff upload  -> mặc định `True` (đã tin cậy).
          - role khác upload       -> `False` (chờ admin verify).
          - Nếu client gửi `is_verified` trong body thì tôn trọng giá trị đó.
        """
        doctor = self.doctors.find_by_id(doctor_id)
        if not doctor:
            raise NotFoundException("errors.not_found")

        self._check_permission(actor, doctor_id)

        # Validate document_type
        doc_type = data.get("document_type")
        if doc_type not in DOCUMENT_TYPES:
            raise ValidationException({"document_type": "invalid_choice"})

        # Check for duplicate license document (only one active license)
        if doc_type == "license":
            existing = self.documents.find_by_type(doctor_id, "license")
            if existing:
                raise ValidationException({
                    "document_type": "duplicate_license",
                    "message": "Bác sĩ đã có giấy phép hành nghề. Vui lòng cập nhật tài liệu hiện có.",
                })

        # Quyết định is_verified mặc định:
        # - Actor là admin/staff (đã qua _check_permission duyệt rồi) -> True.
        # - Ngược lại -> False.
        # Client có thể override bằng cách gửi `is_verified` trong body (vd khi import hàng loạt).
        if "is_verified" in data:
            is_verified = bool(data["is_verified"])
        else:
            is_verified = bool(
                actor
                and actor.has_role(Role.ADMIN, Role.STAFF)
            )

        document = DoctorDocument(
            doctor_id=doctor_id,
            document_type=doc_type,
            title=data["title"],
            object_key=data.get("object_key"),
            issue_date=data.get("issue_date"),
            expiry_date=data.get("expiry_date"),
            is_verified=is_verified,
        )

        self.documents.add(document)
        # Commit để DB sinh `id`/`created_at` và ghi row vật lý — nếu không commit thì
        # response trả về `id: null` và FE lỗi trang sẽ không thấy tài liệu.
        self.documents.commit()
        return document

    def update_document(self, actor, document_id, data):
        """Cập nhật tài liệu. Tự xóa object cũ trên R2 khi `object_key` đổi / xoá."""
        doc = self.documents.find_by_id(document_id)
        if not doc:
            raise NotFoundException("errors.not_found")

        self._check_permission(actor, doc.doctor_id)

        # Snapshot key cũ trước khi gán — để xóa object trên R2 sau commit.
        old_object_key = doc.object_key
        new_object_key = data.get("object_key", old_object_key)

        # Update fields
        updatable = ["title", "object_key", "issue_date", "expiry_date", "is_verified"]
        for field in updatable:
            if field in data:
                setattr(doc, field, data[field])

        # Khi gán object_key mới hoặc xoá (None) thì cache URL cũ không còn
        # hợp lệ -> xoá để to_dict() tự derive lại presigned GET.
        if "object_key" in data and data["object_key"] != old_object_key:
            doc.url = None

        result = self.documents.update(doc)
        # Cleanup R2 chạy SAU commit. Lỗi R2 không rollback DB.
        self._cleanup_old_object(old_object_key, new_object_key)
        return result

    def delete_document(self, actor, document_id):
        """Xóa tài liệu. Tự xóa object trên R2 (best-effort) sau khi commit DB."""
        doc = self.documents.find_by_id(document_id)
        if not doc:
            raise NotFoundException("errors.not_found")

        self._check_permission(actor, doc.doctor_id)

        # Snapshot key trước khi xóa.
        old_object_key = doc.object_key
        self.documents.delete(doc)
        # Cleanup R2 chạy SAU commit.
        self._cleanup_old_object(old_object_key, None)

    def verify_document(self, actor, document_id):
        """Xác minh tài liệu (chỉ admin)."""
        doc = self.documents.find_by_id(document_id)
        if not doc:
            raise NotFoundException("errors.not_found")

        self._check_admin_only(actor)
        doc.is_verified = True
        return self.documents.update(doc)

    def get_expiring_documents(self, actor, days=30):
        """Lấy danh sách tài liệu sắp hết hạn (chỉ admin)."""
        self._check_admin_only(actor)
        return self.documents.find_expiring_documents(days)

    def get_unverified_documents(self, actor):
        """Lấy danh sách tài liệu chưa xác minh (chỉ admin)."""
        self._check_admin_only(actor)
        return self.documents.find_unverified_documents()
'''
import pathlib
pathlib.Path('app/services/doctor_document_service.py').write_text(content, encoding='utf-8')
# Verify
data = pathlib.Path('app/services/doctor_document_service.py').read_bytes()
text = data.decode('utf-8')
print('Wrote', len(text), 'chars')
print('first 100 chars:', text[:100])