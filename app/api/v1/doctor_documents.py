"""Controller quản lý tài liệu bác sĩ.

Cung cấp:
  - POST   /api/v1/doctors/<doctor_id>/documents       -> tạo tài liệu mới
  - GET    /api/v1/doctors/<doctor_id>/documents       -> danh sách tài liệu
  - GET    /api/v1/doctors/<doctor_id>/documents/<id>  -> chi tiết tài liệu
  - PATCH  /api/v1/doctors/<doctor_id>/documents/<id>  -> cập nhật tài liệu
  - DELETE /api/v1/doctors/<doctor_id>/documents/<id>  -> xóa tài liệu
  - POST   /api/v1/doctors/<doctor_id>/documents/<id>/verify -> xác minh tài liệu

Admin endpoints:
  - GET    /api/v1/documents/expiring      -> tài liệu sắp hết hạn
  - GET    /api/v1/documents/unverified    -> tài liệu chưa xác minh
"""
from flask import Blueprint

from ...common.response import success_response
from ...common.roles import Permission
from ...errors import ValidationException
from ...middleware import (
    Field,
    current_user,
    require_permission,
    validate_body,
    validate_query,
    validated,
    validated_query,
)
from ...services.doctor_document_service import DoctorDocumentService

bp = Blueprint("doctor_documents", __name__, url_prefix="/api/v1")

_service = DoctorDocumentService()


# === LIST ===
@bp.get("/doctors/<int:doctor_id>/documents")
@require_permission(Permission.DEPARTMENT_MANAGE)
@validate_query(
    {
        "document_type": Field(str, required=False),
    }
)
def list_documents(doctor_id):
    q = validated_query()
    documents = _service.list_documents(
        actor=current_user(),
        doctor_id=doctor_id,
        document_type=q.get("document_type"),
    )
    return success_response([d.to_dict() for d in documents])


# === GET ONE ===
@bp.get("/doctors/<int:doctor_id>/documents/<int:document_id>")
@require_permission(Permission.DEPARTMENT_MANAGE)
def get_document(doctor_id, document_id):
    document = _service.get_document(
        actor=current_user(),
        document_id=document_id,
    )
    return success_response(document.to_dict())


# === CREATE ===
@bp.post("/doctors/<int:doctor_id>/documents")
@require_permission(Permission.DEPARTMENT_MANAGE)
@validate_body(
    {
        "document_type": Field(str, required=True),
        "title": Field(str, required=True, min_length=1, max_length=255),
        "object_key": Field(str, required=False, max_length=512),
        "issue_date": Field(str, required=False, max_length=10),
        "expiry_date": Field(str, required=False, max_length=10),
        # Tùy chọn: client có thể override is_verified. Nếu không gửi,
        # BE tự set theo role:
        #   - admin/department_head → True (đã tin cậy)
        #   - role khác              → False (chờ admin verify)
        "is_verified": Field(bool, required=False),
    }
)
def create_document(doctor_id):
    from datetime import date

    data = dict(validated())

    # Parse dates
    for field in ["issue_date", "expiry_date"]:
        if field in data and data[field]:
            try:
                data[field] = date.fromisoformat(data[field])
            except ValueError:
                raise ValidationException({field: "invalid_date_format"})

    document = _service.create_document(
        actor=current_user(),
        doctor_id=doctor_id,
        data=data,
    )
    return success_response(
        document.to_dict(),
        status_code=201,
    )


# === UPDATE ===
@bp.patch("/doctors/<int:doctor_id>/documents/<int:document_id>")
@require_permission(Permission.DEPARTMENT_MANAGE)
@validate_body(
    {
        "title": Field(str, required=False, min_length=1, max_length=255),
        "object_key": Field(str, required=False, max_length=512, nullable=True),
        "issue_date": Field(str, required=False, max_length=10),
        "expiry_date": Field(str, required=False, max_length=10),
        "is_verified": Field(bool, required=False),
    }
)
def update_document(doctor_id, document_id):
    from datetime import date

    data = dict(validated())

    # Parse dates
    for field in ["issue_date", "expiry_date"]:
        if field in data and data[field]:
            try:
                data[field] = date.fromisoformat(data[field])
            except ValueError:
                raise ValidationException({field: "invalid_date_format"})

    if not data:
        raise ValidationException(details={"_body": "no_fields"})

    document = _service.update_document(
        actor=current_user(),
        document_id=document_id,
        data=data,
    )
    return success_response(document.to_dict())


# === DELETE ===
@bp.delete("/doctors/<int:doctor_id>/documents/<int:document_id>")
@require_permission(Permission.DEPARTMENT_MANAGE)
def delete_document(doctor_id, document_id):
    _service.delete_document(
        actor=current_user(),
        document_id=document_id,
    )
    return success_response(message="Xóa tài liệu thành công")


# === VERIFY ===
@bp.post("/doctors/<int:doctor_id>/documents/<int:document_id>/verify")
@require_permission(Permission.DEPARTMENT_MANAGE)
def verify_document(doctor_id, document_id):
    document = _service.verify_document(
        actor=current_user(),
        document_id=document_id,
    )
    return success_response(document.to_dict(), message="Xác minh tài liệu thành công")


# === ADMIN: Expiring Documents ===
@bp.get("/documents/expiring")
@require_permission(Permission.DEPARTMENT_MANAGE)
@validate_query(
    {
        "days": Field(int, required=False, default=30, minimum=1, maximum=365),
    }
)
def get_expiring_documents():
    q = validated_query()
    documents = _service.get_expiring_documents(
        actor=current_user(),
        days=q["days"],
    )
    return success_response(
        [d.to_dict() for d in documents],
        message=f"Tài liệu sắp hết hạn trong {q['days']} ngày",
    )


# === ADMIN: Unverified Documents ===
@bp.get("/documents/unverified")
@require_permission(Permission.DEPARTMENT_MANAGE)
def get_unverified_documents():
    documents = _service.get_unverified_documents(actor=current_user())
    return success_response([d.to_dict() for d in documents])
