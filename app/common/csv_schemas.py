"""Khai báo schema cho các file CSV export.

Mục đích:
  - Gom toàn bộ "định nghĩa cột" và "format ô" vào một chỗ, tách khỏi service /
    controller để:
      1. Đổi thứ tự/nhãn cột không phải đụng vào service.
      2. Tái sử dụng được cho nhiều endpoint export (khoa, bác sĩ, bệnh nhân…).
      3. Dễ test (đây là pure functions / data, không cần DB / Flask app).

Quy ước chung:
  - Cột được nhóm theo "phần nghiệp vụ" của model tương ứng (Phần 1, 2, 5).
  - Nhãn tiếng Việt có dấu + kèm key tiếng Anh trong ngoặc đơn để FE/PM đọc lại
    dễ dò ra field nào trong JSON, tránh phải tra bảng mapping.
  - Date hiển thị theo `dd/mm/yyyy` (phù hợp VN), datetime ISO `dd/mm/yyyy HH:MM`.
  - Boolean render `"Có"` / `"Không"`; array render `"; "` joined.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Mapping


# --------------------------------------------------------------------------- #
#  Helpers render                                                              #
# --------------------------------------------------------------------------- #

# Lookup gender: male/female/other -> tiếng Việt. Tránh hardcode ở view/Jinja.
_GENDER_LABELS = {
    "male": "Nam",
    "female": "Nữ",
    "other": "Khác",
}

# Lookup employment type (đồng bộ với `models/doctor.py` enum nếu sau này đổi).
_EMPLOYMENT_LABELS = {
    "full_time": "Toàn thời gian",
    "part_time": "Bán thời gian",
    "contract": "Hợp đồng",
}

_YES_NO = {"yes": "Có", "no": "Không"}


def _fmt_date(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.strftime("%d/%m/%Y %H:%M")
    if isinstance(v, date):
        return v.strftime("%d/%m/%Y")
    return str(v)


def _fmt_bool(v: Any) -> str:
    if v is None:
        return ""
    return _YES_NO["yes"] if v else _YES_NO["no"]


def _fmt_list(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (list, tuple, set)):
        return "; ".join(str(x) for x in v)
    return str(v)


def _fmt_enum(labels: Mapping[str, str]) -> Any:
    """Trả về formatter cho enum có lookup table."""

    def _f(v):
        if v is None or v == "":
            return ""
        return labels.get(str(v), str(v))

    return _f


# --------------------------------------------------------------------------- #
#  Schema export bác sĩ theo khoa                                             #
# --------------------------------------------------------------------------- #

# Mỗi entry: (key, header_label_vi_plus_en_key, formatter).
# Formatter trả "" cho None để ô trống, không phải "None".
DOCTOR_CSV_COLUMNS = [
    # === Thông tin chung ===
    ("id", "ID (id)", lambda v: "" if v is None else str(v)),
    ("full_name", "Họ tên (full_name)", lambda v: "" if v is None else str(v)),
    ("title", "Chức danh (title)", lambda v: "" if v is None else str(v)),
    ("department_id", "Mã khoa (department_id)", lambda v: "" if v is None else str(v)),
    (
        "is_active",
        "Đang hoạt động (is_active)",
        _fmt_bool,
    ),

    # === Phần 1: Thông tin cá nhân ===
    ("phone", "Số điện thoại (phone)", lambda v: "" if v is None else str(v)),
    ("email", "Email (email)", lambda v: "" if v is None else str(v)),
    ("date_of_birth", "Ngày sinh (date_of_birth)", _fmt_date),
    ("gender", "Giới tính (gender)", _fmt_enum(_GENDER_LABELS)),
    ("address", "Địa chỉ (address)", lambda v: "" if v is None else str(v)),

    # === Phần 2: Thông tin chuyên môn ===
    (
        "license_number",
        "Số giấy phép hành nghề (license_number)",
        lambda v: "" if v is None else str(v),
    ),
    ("license_issue_date", "Ngày cấp GPHN (license_issue_date)", _fmt_date),
    ("license_expiry_date", "Ngày hết hạn GPHN (license_expiry_date)", _fmt_date),
    (
        "specialization",
        "Chuyên khoa chính (specialization)",
        lambda v: "" if v is None else str(v),
    ),
    ("sub_specializations", "Chuyên khoa phụ (sub_specializations)", _fmt_list),
    ("education", "Học vấn (education)", _fmt_list),
    ("experience_years", "Số năm kinh nghiệm (experience_years)", lambda v: "" if v is None else str(v)),
    (
        "training_institutions",
        "Nơi đào tạo (training_institutions)",
        _fmt_list,
    ),

    # === Phần 5: Thông tin hành chính ===
    (
        "employment_type",
        "Loại hợp đồng (employment_type)",
        _fmt_enum(_EMPLOYMENT_LABELS),
    ),
    ("hire_date", "Ngày vào làm (hire_date)", _fmt_date),
    ("contract_end_date", "Ngày kết thúc HĐ (contract_end_date)", _fmt_date),
    (
        "is_accepting_new_patients",
        "Đang nhận bệnh nhân mới (is_accepting_new_patients)",
        _fmt_bool,
    ),

    # === Metadata (audit) ===
    ("created_at", "Ngày tạo (created_at)", _fmt_date),
    ("updated_at", "Ngày cập nhật (updated_at)", _fmt_date),
]


def doctor_column_keys() -> list[str]:
    """Chỉ trả về danh sách key (string) theo đúng thứ tự đã khai báo."""
    return [c[0] for c in DOCTOR_CSV_COLUMNS]


def doctor_header_labels() -> dict[str, str]:
    """Map key -> nhãn hiển thị ở header CSV (tiếng Việt + key EN)."""
    return {c[0]: c[1] for c in DOCTOR_CSV_COLUMNS}


def format_doctor_row(doctor_dict: Mapping[str, Any]) -> dict[str, str]:
    """Chuẩn hoá 1 row dict đã lấy từ `Doctor.to_dict()` -> dict[str, str].

    Bỏ qua các key không có trong schema để file CSV ổn định khi model thêm field.
    """
    out: dict[str, str] = {}
    for key, _label, formatter in DOCTOR_CSV_COLUMNS:
        out[key] = formatter(doctor_dict.get(key))
    return out


__all__ = [
    "DOCTOR_CSV_COLUMNS",
    "doctor_column_keys",
    "doctor_header_labels",
    "format_doctor_row",
]
