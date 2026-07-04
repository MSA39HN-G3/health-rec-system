"""Controller quản lý khoa/chuyên khoa.

Bảo vệ theo PERMISSION `department:manage` (cả admin và department_head đều qua,
đúng triết lý RBAC DB-driven). Cung cấp:
  - POST  /api/v1/departments        -> tạo khoa mới (chọn trưởng khoa tùy chọn)
  - GET   /api/v1/departments        -> danh sách khoa (phân trang)
  - GET   /api/v1/departments/stats  -> thống kê số lượng khoa
  - PATCH /api/v1/departments/<id>   -> cập nhật từng phần (gồm ảnh, kĩ thuật chuyên môn)

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


@bp.get("/stats")
@require_permission(Permission.DEPARTMENT_MANAGE)
def department_stats():
    """Thống kê số lượng khoa: tổng / đang hoạt động / tạm dừng."""
    return success_response(_service.get_stats())


@bp.post("")
@require_permission(Permission.DEPARTMENT_MANAGE)
@validate_body(
    {
        "name": Field(str, required=True, min_length=1, max_length=255),
        "location": Field(str, required=False, max_length=255),
        "description": Field(str, required=False, max_length=5000),
        "head_doctor_id": Field(int, required=False, minimum=1),
        # is_active: bật/tắt khoa ngay khi tạo. Mặc định False (khoa tạo ra ở
        # trạng thái tạm dừng). Nếu client gửi True mà không có head_doctor_id
        # hợp lệ -> BE trả 400 (kiểm tra ở service, không phải validation 422
        # vì đây là ràng buộc nghiệp vụ liên quan 2 field).
        "is_active": Field(bool, required=False, default=False),
    }
)
def create_department():
    # Lưu ý: mã khoa ("CK-NNN") do hệ thống tự sinh, không nhận từ client.
    data = validated()
    keywords = _string_list("keywords", max_items=50, max_len=64)
    conditions = _string_list("conditions", max_items=50, max_len=128)
    ai_metadata = _object("ai_metadata")
    department = _service.create_department(
        name=data["name"],
        location=data.get("location"),
        description=data.get("description"),
        keywords=keywords,
        conditions=conditions,
        ai_metadata=ai_metadata,
        head_doctor_id=data.get("head_doctor_id"),
        is_active=data["is_active"],
    )
    return success_response(
        department.to_dict(),
        message=translate("messages.department_created"),
        status_code=201,
    )


@bp.patch("/<int:department_id>")
@require_permission(Permission.DEPARTMENT_MANAGE)
@validate_body(
    {
        "name": Field(str, required=False, min_length=1, max_length=255),
        "location": Field(str, required=False, max_length=255, nullable=True),
        "avatar_url": Field(str, required=False, max_length=512, nullable=True),
        "avatar_object_key": Field(
            str, required=False, max_length=512, nullable=True
        ),
        "description": Field(str, required=False, max_length=5000, nullable=True),
        "head_doctor_id": Field(int, required=False, minimum=1, nullable=True),
    }
)
def update_department(department_id):
    # Cập nhật TỪNG PHẦN: chỉ field nào có trong body mới bị thay đổi.
    # - `code` không cho sửa (hệ thống cấp); `is_active` suy ra từ `head_doctor_id`.
    # - field nhận null (location/avatar_url/avatar_object_key/description/head_doctor_id)
    #   -> xóa giá trị.
    changes = dict(validated())

    # Array/object validate thủ công, chỉ áp dụng khi field thực sự có trong body.
    raw = _raw_body()
    if "keywords" in raw:
        changes["keywords"] = _string_list("keywords", max_items=50, max_len=64)
    if "conditions" in raw:
        changes["conditions"] = _string_list("conditions", max_items=50, max_len=128)
    if "techniques" in raw:
        changes["techniques"] = _string_list("techniques", max_items=100, max_len=255)
    if "ai_metadata" in raw:
        changes["ai_metadata"] = _object("ai_metadata")

    if not changes:
        raise ValidationException(details={"_body": "no_fields"})

    department = _service.update_department(department_id, **changes)
    return success_response(
        department.to_dict(),
        message=translate("messages.department_updated"),
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
