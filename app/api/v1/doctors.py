"""Controller quản lý bác sĩ - CRUD operations.

Cung cấp đầy đủ các endpoint:
  - POST   /api/v1/doctors              -> tạo bác sĩ mới
  - GET    /api/v1/doctors              -> danh sách bác sĩ (phân trang)
  - GET    /api/v1/doctors/<id>         -> chi tiết bác sĩ
  - PATCH  /api/v1/doctors/<id>         -> cập nhật bác sĩ
  - DELETE /api/v1/doctors/<id>         -> xóa bác sĩ (soft delete)
  - GET    /api/v1/doctors/search       -> tìm kiếm bác sĩ
  - GET    /api/v1/doctors/expiring-licenses -> giấy phép sắp hết hạn

Phân quyền:
  - admin             -> toàn quyền CRUD
  - department_head   -> chỉ xem/sửa bác sĩ thuộc khoa của mình
"""
from flask import Blueprint, request

from ...common.response import paginated_response, success_response
from ...common.roles import Permission
from ...errors import ValidationException
from ...i18n import translate
from ...middleware import (
    Field,
    current_user,
    require_permission,
    validate_body,
    validate_query,
    validated,
    validated_query,
)
from ...services.doctor_service import DoctorService

bp = Blueprint("doctors", __name__, url_prefix="/api/v1/doctors")

_service = DoctorService()


# === CREATE ===
@bp.post("")
@require_permission(Permission.DEPARTMENT_MANAGE)
@validate_body(
    {
        "full_name": Field(str, required=True, min_length=1, max_length=255),
        "department_id": Field(int, required=True, minimum=1),
        "title": Field(str, required=False, max_length=64),
        # Phần 1: Thông tin cá nhân
        "phone": Field(str, required=False, max_length=32),
        "email": Field(str, required=False, max_length=255),
        "avatar_object_key": Field(str, required=False, max_length=512),
        "date_of_birth": Field(str, required=False, max_length=10),  # ISO date string
        "gender": Field(str, required=False, max_length=32),
        "address": Field(str, required=False, max_length=1000),
        # Phần 2: Thông tin chuyên môn
        "license_number": Field(str, required=False, max_length=64),
        "license_issue_date": Field(str, required=False, max_length=10),
        "license_expiry_date": Field(str, required=False, max_length=10),
        "specialization": Field(str, required=False, max_length=255),
        "sub_specializations": Field(list, required=False),  # Array validation done manually
        "education": Field(list, required=False),
        "experience_years": Field(int, required=False, minimum=0),
        "training_institutions": Field(list, required=False),
        # Phần 5: Thông tin hành chính
        "employment_type": Field(str, required=False, max_length=32),
        "hire_date": Field(str, required=False, max_length=10),
        "contract_end_date": Field(str, required=False, max_length=10),
        "is_accepting_new_patients": Field(bool, required=False, default=True),
    }
)
def create_doctor():
    data = _parse_dates(validated())

    # Validate arrays
    data["sub_specializations"] = _string_list("sub_specializations", max_items=20, max_len=255)
    data["education"] = _string_list("education", max_items=10, max_len=255)
    data["training_institutions"] = _string_list("training_institutions", max_items=10, max_len=255)

    # Validate gender
    if data.get("gender") and data["gender"] not in ("male", "female", "other"):
        raise ValidationException({"gender": "invalid_choice"})

    # Validate employment_type
    if data.get("employment_type") and data["employment_type"] not in ("full_time", "part_time", "contract"):
        raise ValidationException({"employment_type": "invalid_choice"})

    doctor = _service.create_doctor(
        actor=current_user(),
        data=data,
    )
    return success_response(
        doctor.to_dict(),
        message=translate("messages.doctor_created"),
        status_code=201,
    )


# === LIST ===
@bp.get("")
@require_permission(Permission.DEPARTMENT_MANAGE)
@validate_query(
    {
        "page": Field(int, required=False, default=1, minimum=1),
        "size": Field(int, required=False, default=20, minimum=1, maximum=100),
        "department_id": Field(int, required=False, minimum=1),
        "is_active": Field(bool, required=False),
    }
)
def list_doctors():
    q = validated_query()
    items, total, scope = _service.list_doctors(
        actor=current_user(),
        page=q["page"],
        size=q["size"],
        department_id=q.get("department_id"),
    )
    return paginated_response(
        [d.to_dict() for d in items],
        page=q["page"],
        size=q["size"],
        total=total,
        message=scope["label"],
    )


# === GET ONE ===
@bp.get("/<int:doctor_id>")
@require_permission(Permission.DEPARTMENT_MANAGE)
def get_doctor(doctor_id):
    doctor = _service.get_doctor(
        actor=current_user(),
        doctor_id=doctor_id,
    )
    include_stats = request.args.get("include_stats", "false").lower() == "true"
    include_ratings = request.args.get("include_ratings", "false").lower() == "true"
    return success_response(doctor.to_dict(include_stats=include_stats, include_ratings=include_ratings))


# === UPDATE ===
@bp.patch("/<int:doctor_id>")
@require_permission(Permission.DEPARTMENT_MANAGE)
@validate_body(
    {
        "full_name": Field(str, required=False, min_length=1, max_length=255),
        "department_id": Field(int, required=False, minimum=1),
        "title": Field(str, required=False, max_length=64, nullable=True),
        "is_active": Field(bool, required=False),
        # Phần 1: Thông tin cá nhân
        "phone": Field(str, required=False, max_length=32, nullable=True),
        "email": Field(str, required=False, max_length=255, nullable=True),
        "avatar_object_key": Field(str, required=False, max_length=512, nullable=True),
        "date_of_birth": Field(str, required=False, max_length=10),
        "gender": Field(str, required=False, max_length=32),
        "address": Field(str, required=False, max_length=1000, nullable=True),
        # Phần 2: Thông tin chuyên môn
        "license_number": Field(str, required=False, max_length=64, nullable=True),
        "license_issue_date": Field(str, required=False, max_length=10),
        "license_expiry_date": Field(str, required=False, max_length=10),
        "specialization": Field(str, required=False, max_length=255, nullable=True),
        "sub_specializations": Field(list, required=False),
        "education": Field(list, required=False),
        "experience_years": Field(int, required=False, minimum=0),
        "training_institutions": Field(list, required=False),
        # Phần 5: Thông tin hành chính
        "employment_type": Field(str, required=False, max_length=32),
        "hire_date": Field(str, required=False, max_length=10),
        "contract_end_date": Field(str, required=False, max_length=10),
        "is_accepting_new_patients": Field(bool, required=False),
    }
)
def update_doctor(doctor_id):
    data = _parse_dates(validated())

    # Validate arrays if provided
    raw = _raw_body()
    if "sub_specializations" in raw:
        data["sub_specializations"] = _string_list("sub_specializations", max_items=20, max_len=255)
    if "education" in raw:
        data["education"] = _string_list("education", max_items=10, max_len=255)
    if "training_institutions" in raw:
        data["training_institutions"] = _string_list("training_institutions", max_items=10, max_len=255)

    # Validate gender
    if data.get("gender") and data["gender"] not in ("male", "female", "other"):
        raise ValidationException({"gender": "invalid_choice"})

    # Validate employment_type
    if data.get("employment_type") and data["employment_type"] not in ("full_time", "part_time", "contract"):
        raise ValidationException({"employment_type": "invalid_choice"})

    if not data:
        raise ValidationException(details={"_body": "no_fields"})

    doctor = _service.update_doctor(
        actor=current_user(),
        doctor_id=doctor_id,
        data=data,
    )
    return success_response(
        doctor.to_dict(),
        message=translate("messages.doctor_updated"),
    )


# === DELETE (Soft Delete) ===
@bp.delete("/<int:doctor_id>")
@require_permission(Permission.DEPARTMENT_MANAGE)
def delete_doctor(doctor_id):
    _service.delete_doctor(
        actor=current_user(),
        doctor_id=doctor_id,
    )
    return success_response(
        message=translate("messages.doctor_deleted"),
    )


# === SEARCH ===
@bp.get("/search")
@require_permission(Permission.DEPARTMENT_MANAGE)
@validate_query(
    {
        "q": Field(str, required=True, min_length=1),
        "page": Field(int, required=False, default=1, minimum=1),
        "size": Field(int, required=False, default=20, minimum=1, maximum=100),
        "department_id": Field(int, required=False, minimum=1),
    }
)
def search_doctors():
    q = validated_query()
    items, total = _service.search_doctors(
        actor=current_user(),
        keyword=q["q"],
        page=q["page"],
        size=q["size"],
        department_id=q.get("department_id"),
    )
    return paginated_response(
        [d.to_dict() for d in items],
        page=q["page"],
        size=q["size"],
        total=total,
        message=f"Kết quả tìm kiếm: '{q['q']}'",
    )


# === EXPIRING LICENSES ===
@bp.get("/expiring-licenses")
@require_permission(Permission.DEPARTMENT_MANAGE)
@validate_query(
    {
        "days": Field(int, required=False, default=30, minimum=1, maximum=365),
    }
)
def get_expiring_licenses():
    q = validated_query()
    doctors = _service.get_expiring_licenses(
        actor=current_user(),
        days=q["days"],
    )
    return success_response(
        [d.to_dict() for d in doctors],
        message=f"Giấy phép hành nghề sắp hết hạn trong {q['days']} ngày",
    )


# === HELPER FUNCTIONS ===

def _raw_body():
    body = request.get_json(silent=True)
    return body if isinstance(body, dict) else {}


def _string_list(field, max_items, max_len):
    """Validate một trường array<string> từ JSON body."""
    raw = _raw_body().get(field)
    if raw is None:
        return []
    if not isinstance(raw, list) or len(raw) > max_items:
        raise ValidationException(details={field: "invalid_list"})
    cleaned = []
    for item in raw:
        if not isinstance(item, str):
            raise ValidationException(details={field: "invalid_item"})
        value = item.strip()
        if not (1 <= len(value) <= max_len):
            raise ValidationException(details={field: "invalid_item"})
        cleaned.append(value)
    return cleaned


def _parse_dates(data):
    """Parse ISO date strings to date objects."""
    from datetime import date

    date_fields = [
        "date_of_birth", "license_issue_date", "license_expiry_date",
        "hire_date", "contract_end_date"
    ]
    result = dict(data)
    for field in date_fields:
        if field in result and result[field]:
            try:
                result[field] = date.fromisoformat(result[field])
            except ValueError:
                raise ValidationException({field: "invalid_date_format"})
    return result
