"""Controller quản lý khoa/chuyên khoa.

Bảo vệ theo PERMISSION `department:manage` (cả admin và department_head đều qua,
đúng triết lý RBAC DB-driven). Bước đầu cung cấp:
  - POST /api/v1/departments  -> tạo khoa mới (chọn trưởng khoa tùy chọn)
  - GET  /api/v1/departments  -> danh sách khoa (phân trang)

Lưu ý: middleware `Field` chỉ validate kiểu scalar (string/int/...), KHÔNG hỗ trợ
array/object. Vì vậy các trường `keywords`/`conditions`/`ai_metadata` được validate
thủ công từ JSON body, raise ValidationException để giữ response 422 đồng nhất.
"""
from flask import Blueprint, request

from ...common.response import paginated_response, success_response
from ...common.roles import Permission
from ...errors import ValidationException
from ...i18n import translate
from ...middleware import (
    Field,
    require_permission,
    validate_body,
    validate_query,
    validated,
    validated_query,
)
from ...services.department_service import DepartmentService

bp = Blueprint("departments", __name__, url_prefix="/api/v1/departments")

_service = DepartmentService()


@bp.get("")
@require_permission(Permission.DEPARTMENT_MANAGE)
@validate_query(
    {
        "page": Field(int, required=False, default=1, minimum=1),
        "size": Field(int, required=False, default=20, minimum=1, maximum=100),
    }
)
def list_departments():
    q = validated_query()
    items, total = _service.list_departments(q["page"], q["size"])
    return paginated_response(
        [d.to_dict() for d in items],
        page=q["page"],
        size=q["size"],
        total=total,
    )


@bp.post("")
@require_permission(Permission.DEPARTMENT_MANAGE)
@validate_body(
    {
        "code": Field(str, required=True, min_length=1, max_length=32),
        "name": Field(str, required=True, min_length=1, max_length=255),
        "description": Field(str, required=False, max_length=5000),
        "head_doctor_id": Field(int, required=False, minimum=1),
    }
)
def create_department():
    data = validated()
    keywords = _string_list("keywords", max_items=50, max_len=64)
    conditions = _string_list("conditions", max_items=50, max_len=128)
    ai_metadata = _object("ai_metadata")
    department = _service.create_department(
        code=data["code"],
        name=data["name"],
        description=data.get("description"),
        keywords=keywords,
        conditions=conditions,
        ai_metadata=ai_metadata,
        head_doctor_id=data.get("head_doctor_id"),
    )
    return success_response(
        department.to_dict(),
        message=translate("messages.department_created"),
        status_code=201,
    )


def _raw_body():
    body = request.get_json(silent=True)
    return body if isinstance(body, dict) else {}


def _string_list(field, max_items, max_len):
    """Validate một trường array<string> từ JSON body (Field không hỗ trợ array)."""
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


def _object(field):
    """Validate một trường object tự do từ JSON body."""
    raw = _raw_body().get(field)
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValidationException(details={field: "must_be_object"})
    return raw
