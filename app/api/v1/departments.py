"""Controller quản lý khoa/chuyên khoa.

Bảo vệ theo PERMISSION `department:manage` (cả admin và department_head đều qua,
đúng triết lý RBAC DB-driven). Cung cấp:
  - POST  /api/v1/departments        -> tạo khoa mới (chọn trưởng khoa tùy chọn)
  - GET   /api/v1/departments        -> danh sách khoa (phân trang)
  - GET   /api/v1/departments/stats  -> thống kê số lượng khoa
  - GET   /api/v1/departments/<id>   -> chi tiết 1 khoa (xem FE_DEPARTMENT_DETAIL)
  - GET   /api/v1/departments/<id>/doctors
                                    -> danh sách bác sĩ thuộc khoa + stats
                                    (?format=csv -> download file CSV)
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


@bp.get("/<int:department_id>")
@require_permission(Permission.DEPARTMENT_MANAGE)
def get_department(department_id):
    """Chi tiết 1 khoa."""
    department = _service.get_department(department_id)
    return success_response(department.to_dict())


@bp.get("/<int:department_id>/doctors")
@require_permission(Permission.DEPARTMENT_MANAGE)
@validate_query(
    {
        "page": Field(int, required=False, default=1, minimum=1),
        # size mặc định 10, max 50 (theo spec FE_DEPARTMENT_DETAIL.md §3.2).
        "size": Field(int, required=False, default=10, minimum=1, maximum=50),
        "q": Field(str, required=False, max_length=100),
        "qualification": Field(str, required=False, max_length=255),
        # `format=csv` -> trả file CSV trực tiếp (xem §5 FE_DEPARTMENT_DETAIL).
        # Không truyền hoặc `format=json` -> giữ response JSON mặc định.
        "format": Field(str, required=False, default="json"),
    }
)
def list_department_doctors(department_id):
    """Danh sách bác sĩ thuộc khoa (JSON) HOẶC export CSV (?format=csv).

    Mặc định trả JSON:
      `{stats: {...}, doctors: [...]}` + meta phân trang (xem mục 3 spec).

    Nếu `?format=csv` -> trả file `doctors_<code>_<timestamp>.csv` với BOM
    UTF-8 và toàn bộ field của Doctor (trừ quan hệ nặng). Lúc này bỏ qua
    pagination — file chứa toàn bộ bác sĩ khớp filter `q` / `qualification`.
    """
    q = validated_query()
    fmt = (q.get("format") or "json").lower()

    if fmt == "csv":
        return _export_doctors_csv(
            department_id,
            q=q.get("q"),
            qualification=q.get("qualification"),
        )

    if fmt != "json":
        # Spec hiện chỉ cho phép `json` (mặc định) hoặc `csv`. Mọi giá trị
        # khác -> 422 để FE dễ debug.
        from ...errors import ValidationException

        raise ValidationException(details={"format": "invalid_format"})

    payload = _service.list_department_doctors(
        department_id,
        page=q["page"],
        size=q["size"],
        q=q.get("q"),
        qualification=q.get("qualification"),
    )
    serialized_doctors = [
        serialize_doctor_summary(d) for d in payload["doctors"]
    ]
    data = {
        "stats": payload["stats"],
        "doctors": serialized_doctors,
    }
    return success_response(
        data=data,
        meta={
            "page": q["page"],
            "size": q["size"],
            "totalPage": _total_page(payload["total"], q["size"]),
        },
    )


def _export_doctors_csv(department_id, *, q=None, qualification=None):
    """Sinh Response CSV trả về trực tiếp cho client download."""
    from datetime import datetime, timezone
    from flask import Response

    csv_text, department, total = _service.export_department_doctors_csv(
        department_id, q=q, qualification=qualification
    )

    # Tên file dễ đọc, an toàn cho mọi OS: dùng mã khoa + timestamp UTC.
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    # `code` chỉ chứa A-Z, 0-9 và "-", an toàn để đưa thẳng vào filename.
    filename = f"doctors_{department.code}_{timestamp}.csv"

    return Response(
        csv_text,
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{filename}"; '
                f"filename*=UTF-8''{filename}"
            ),
            "Content-Type": "text/csv; charset=utf-8",
            "X-Export-Total-Rows": str(total),
            # CSV có BOM, vẫn khai báo charset=utf-8 để trình duyệt hiểu.
            "Cache-Control": "no-store",
        },
    )


@bp.post("")
@require_permission(Permission.DEPARTMENT_MANAGE)
@validate_body(
    {
        "name": Field(str, required=True, min_length=1, max_length=255),
        "location": Field(str, required=False, max_length=255),
        "description": Field(str, required=False, max_length=5000),
        # `head_doctor_id` đã bỏ theo refactor 1a2b3c4d5e6f — staff quản lý tất
        # cả bác sĩ, không cần gắn một user/doctor cụ thể làm trưởng.
        # `is_active`: bật/tắt khoa ngay khi tạo (mặc định False). Không còn
        # ràng buộc "is_active=true phải có head_doctor".
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
        # `head_doctor_id` đã bỏ theo refactor 1a2b3c4d5e6f.
        # FE có thể bật/tắt khoa trực tiếp qua `is_active`.
        "is_active": Field(bool, required=False, nullable=True),
    }
)
def update_department(department_id):
    # Cập nhật TỪNG PHẦN: chỉ field nào có trong body mới bị thay đổi.
    # - `code` không cho sửa (hệ thống cấp).
    # - field nhận null (location/avatar_url/avatar_object_key/description) -> xóa.
    # - `is_active`: gửi true/false để bật/tắt.
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


def _total_page(total, size):
    """Tính tổng số trang (giống helper nội bộ trong common.response)."""
    return (total + size - 1) // size if size else 0


# ==========================================================================
# Helper cho GET /api/v1/departments/{id}/doctors
# (xem docs/FE_DEPARTMENT_DETAIL.md §3.4)
# ==========================================================================

# Nhãn tiếng Việt in hoa cho status bác sĩ — FE render thẳng, không cần i18n.
_DOCTOR_STATUS_LABEL = {
    "available": "ĐANG LÀM VIỆC",
    "on_leave": "ĐANG NGHỈ",
    "in_session": "CÓ LỊCH HẸN",
}

# Map day_of_week của model (0 = CN, 1 = T2, ..., 6 = T7) sang mã 2-chữ VN
# mà FE dùng (xem comment model DoctorSchedule.day_of_week).
_DOW_VI = {
    1: "T2",
    2: "T3",
    3: "T4",
    4: "T5",
    5: "T6",
    6: "T7",
    0: "CN",
}


def _derive_qualification(title):
    """Lấy phần trình độ ngắn gọn từ `title` đầy đủ.

    Quy tắc heuristic: lấy phần TRƯỚC dấu phẩy đầu tiên, hoặc toàn bộ nếu
    không có dấu phẩy. vd "Thạc sĩ, Bác sĩ CKI" -> "Thạc sĩ".
    """
    if not title:
        return None
    return title.split(",", 1)[0].strip() or None


def _derive_experience_display(years):
    if years is None:
        return None
    return f"{years} năm"


def _derive_status(doctor_id, today_count):
    """Suy ra `status` của bác sĩ.

    - `in_session`: có appointment hôm nay với status `checked_in`/`in_session`.
    - `on_leave`:   hiện hệ thống chưa có bảng `doctor_leaves` (TODO). Luôn
                    trả `available` cho case này.
    - `available`:  còn lại (mặc định).
    """
    if today_count and today_count > 0:
        return "in_session"
    return "available"


def _derive_schedule(doctor):
    """Lấy lịch trực gần nhất trong tuần hiện tại của bác sĩ.

    Trả về `{days, period, summary}` hoặc `None` nếu bác sĩ chưa có lịch nào
    đang `is_active`.
    """
    schedules = (
        doctor.schedules.filter_by(is_active=True)
        .order_by("day_of_week", "start_time")
        .all()
    )
    if not schedules:
        return None
    # day_of_week theo model: 0=CN, 1=T2, ..., 6=T7.
    days_set = sorted({s.day_of_week for s in schedules})
    day_labels = [_DOW_VI.get(d) for d in days_set if d in _DOW_VI]

    # Phân loại ca dựa trên giờ bắt đầu của từng schedule.
    periods = []
    for s in schedules:
        h = s.start_time.hour if s.start_time else 12
        if h < 12:
            periods.append("Sáng")
        elif h < 18:
            periods.append("Chiều")
        else:
            periods.append("Tối")

    # Period: lấy mode của start_time.hour. Nếu vừa có "Sáng" vừa có "Chiều"
    # -> "Cả ngày" (bác sĩ làm cả ngày).
    period = None
    if periods:
        unique_periods = set(periods)
        if unique_periods == {"Sáng", "Chiều"} or len(unique_periods) > 1:
            period = "Cả ngày"
        else:
            period = next(iter(unique_periods))

    # Tạo summary kiểu "T2, T4, T6 (Sáng)" — FE có thể dùng luôn.
    if period:
        summary = f"{', '.join(day_labels)} ({period})"
    else:
        summary = ", ".join(day_labels)
    return {"days": day_labels, "period": period, "summary": summary}


def serialize_doctor_summary(doctor):
    """Serialize bác sĩ cho endpoint `/departments/{id}/doctors`.

    Tối ưu cho FE table — chỉ trả các trường tối thiểu cần thiết để render.
    """
    today_count = _count_today_in_session(doctor.id)
    status = _derive_status(doctor.id, today_count)
    return {
        "id": doctor.id,
        "full_name": doctor.full_name,
        "title": doctor.title,
        "qualification": _derive_qualification(doctor.title),
        "experience_years": doctor.experience_years,
        "experience_display": _derive_experience_display(doctor.experience_years),
        "status": status,
        "status_label": _DOCTOR_STATUS_LABEL.get(status, status),
        "schedule": _derive_schedule(doctor),
        "avatar_url": doctor._get_avatar_url(),
        "is_accepting_new_patients": bool(doctor.is_accepting_new_patients),
    }


def _count_today_in_session(doctor_id):
    """Đếm appointment hôm nay của 1 bác sĩ đang ở trạng thái `checked_in` /
    `in_session`. Trả 0 nếu không có.

    Hàm này được gọi 1 lần cho mỗi doctor trong page — chấp nhận được ở mức
    vài chục query nhỏ (N nhỏ theo `size`, max 50). Nếu cần tối ưu hơn nữa,
    có thể bulk-query 1 lần cho cả page (xem doc §3.7 — index đã đề xuất).
    """
    from datetime import date as _date
    from ...models.appointment import Appointment

    return (
        Appointment.query.with_entities(Appointment.id)
        .filter(Appointment.doctor_id == doctor_id)
        .filter(Appointment.appointment_date == _date.today())
        .filter(Appointment.status.in_(("checked_in", "in_session")))
        .limit(1)
        .count()
    )
