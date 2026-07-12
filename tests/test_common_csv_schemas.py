"""Unit test cho schema CSV bác sĩ (`app.common.csv_schemas`).

Mục tiêu: đảm bảo cột được nhóm đúng theo phần Doctor, nhãn tiếng Việt có kèm key
EN, không lẫn field nặng (avatar_url, relations), và formatter chuẩn hoá
date/bool/array sang dạng Excel-friendly (dd/mm/yyyy, "Có"/"Không", "; "-join).
"""
from datetime import date, datetime, timezone

import pytest

from app.common.csv_schemas import (
    DOCTOR_CSV_COLUMNS,
    doctor_column_keys,
    doctor_header_labels,
    format_doctor_row,
)


class TestDoctorCsvSchema:
    """Kiểm tra schema tổng thể — thứ tự cột, nhãn, và shape đầu ra."""

    def test_columns_are_grouped_by_doctor_sections(self):
        # Thứ tự: Thông tin chung -> Phần 1 (cá nhân) -> Phần 2 (chuyên môn)
        #         -> Phần 5 (hành chính) -> Metadata.
        keys = doctor_column_keys()
        # Core / chung ở đầu
        assert keys[0] == "id"
        assert keys[1] == "full_name"

        # Phần 1: phone ngay sau core, KHÔNG có avatar_url.
        section_1_start = keys.index("phone")
        assert "avatar_url" not in keys
        assert "avatar_object_key" not in keys
        assert keys[keys.index("phone") + 1] == "email"
        assert keys[keys.index("address")] == "address"
        assert section_1_start < keys.index("phone") + 5

        # Phần 2 chuyên môn: license_number mở đầu.
        assert keys.index("license_number") < keys.index("specialization")
        assert keys.index("specialization") < keys.index("training_institutions")

        # Phần 5 hành chính: employment_type, hire_date, contract_end_date,
        #                    is_accepting_new_patients liền kề nhau.
        emp_idx = keys.index("employment_type")
        assert keys[emp_idx + 1] == "hire_date"
        assert keys[emp_idx + 2] == "contract_end_date"
        assert keys[emp_idx + 3] == "is_accepting_new_patients"

        # Metadata ở cuối.
        assert keys[-1] == "updated_at"
        assert keys[-2] == "created_at"

    def test_no_heavy_relationships_in_export(self):
        # documents/ratings/statistics là relationship nặng -> phải loại khỏi export.
        keys = doctor_column_keys()
        for forbidden in {"documents", "ratings", "statistics", "department"}:
            assert forbidden not in keys, (
                f"{forbidden!r} không được xuất hiện trong CSV export"
            )

    def test_header_labels_vietnamese_with_english_key(self):
        labels = doctor_header_labels()
        # Bắt buộc phải có dấu + kèm key EN trong ngoặc đơn ở cuối.
        for key, label in labels.items():
            assert label.endswith(f"({key})"), (
                f"Header cho {key!r} phải kết thúc bằng '({key})' để tra được "
                f"trong JSON response. Thực tế: {label!r}"
            )
            # Không được để trống.
            assert len(label) > len(key) + 2

    def test_header_labels_does_not_contain_avatar_terms(self):
        # Khi loại bỏ avatar_url, label cũng phải biến mất.
        labels = doctor_header_labels()
        assert all("avatar" not in v.lower() for v in labels.values())

    def test_unique_column_keys(self):
        keys = doctor_column_keys()
        assert len(keys) == len(set(keys)), "Không được trùng key"


class TestFormatDoctorRow:
    """Formatter từng ô: date/bool/enum/list."""

    def _row(self, **overrides):
        base = {
            "id": 1,
            "full_name": "Trần Thị Minh",
            "title": "BS. CKII",
            "department_id": 5,
            "is_active": True,
            "phone": "0901234567",
            "email": "minh@example.vn",
            "date_of_birth": date(1985, 3, 7),
            "gender": "female",
            "address": "Hà Nội",
            "license_number": "GPHN-123",
            "license_issue_date": date(2015, 6, 1),
            "license_expiry_date": date(2025, 6, 1),
            "specialization": "Nội tiết",
            "sub_specializations": ["Nội tiết thai kỳ", "Đái tháo đường"],
            "education": ["ĐH Y Hà Nội", "ThS Y khoa"],
            "experience_years": 12,
            "training_institutions": ["BV Bạch Mai"],
            "employment_type": "full_time",
            "hire_date": date(2020, 1, 15),
            "contract_end_date": None,
            "is_accepting_new_patients": False,
            "created_at": datetime(2024, 1, 2, 3, 4, tzinfo=timezone.utc),
            "updated_at": datetime(2024, 5, 6, 7, 8, tzinfo=timezone.utc),
            # Các field bị loại khỏi export — formatter vẫn phải BỎ QUA, không lộ ra.
            "avatar_url": "https://cdn.example.com/minh.jpg",
            "documents": [{"id": 99, "name": "fake"}],
        }
        base.update(overrides)
        return base

    def test_date_renders_dd_slash_mm_slash_yyyy(self):
        out = format_doctor_row(self._row())
        assert out["date_of_birth"] == "07/03/1985"
        assert out["license_issue_date"] == "01/06/2015"
        assert out["hire_date"] == "15/01/2020"

    def test_datetime_renders_with_time(self):
        out = format_doctor_row(self._row())
        # datetime cũng theo format dd/mm/yyyy HH:MM.
        assert out["created_at"] == "02/01/2024 03:04"
        assert out["updated_at"] == "06/05/2024 07:08"

    def test_bool_renders_co_khong(self):
        out = format_doctor_row(self._row())
        assert out["is_active"] == "Có"
        assert out["is_accepting_new_patients"] == "Không"

    def test_gender_rendered_vietnamese(self):
        out = format_doctor_row(self._row())
        assert out["gender"] == "Nữ"

    def test_employment_type_rendered_vietnamese(self):
        out = format_doctor_row(self._row())
        assert out["employment_type"] == "Toàn thời gian"

    def test_list_joined_with_semicolon_space(self):
        out = format_doctor_row(self._row())
        assert out["sub_specializations"] == "Nội tiết thai kỳ; Đái tháo đường"
        assert out["education"] == "ĐH Y Hà Nội; ThS Y khoa"
        assert out["training_institutions"] == "BV Bạch Mai"

    def test_none_becomes_empty_string(self):
        out = format_doctor_row(self._row(contract_end_date=None, gender=None))
        assert out["contract_end_date"] == ""
        assert out["gender"] == ""

    def test_unknown_enum_falls_back_to_raw(self):
        # Nếu model sau này thêm enum mới, vẫn render được value thô để tránh
        # mất dữ liệu — chỉ mất đi "label tiếng Việt".
        out = format_doctor_row(self._row(employment_type="locum"))
        assert out["employment_type"] == "locum"

    def test_unknown_extra_keys_are_dropped(self):
        # File CSV phải ổn định schema: avatar_url, documents không được lọt vào.
        out = format_doctor_row(self._row())
        # Cột chỉ đúng theo schema, avatar_url không xuất hiện trong row.
        assert set(out.keys()) == set(doctor_column_keys())
        assert "avatar_url" not in out
        assert "documents" not in out


class TestBuildCsvWithDoctorSchema:
    """Kết hợp schema doctor vào `build_csv` — đảm bảo header + body khớp."""

    def test_full_output_smoke(self):
        from app.common.csv_export import build_csv

        columns = doctor_column_keys()
        labels = doctor_header_labels()
        row = {
            "id": 1,
            "full_name": "Trần Thị Minh",
            "title": "BS. CKII",
            "department_id": 5,
            "is_active": True,
            "phone": "0901234567",
            "email": "minh@example.vn",
            "date_of_birth": date(1985, 3, 7),
            "gender": "female",
            "address": "Hà Nội",
            "license_number": "GPHN-123",
            "license_issue_date": date(2015, 6, 1),
            "license_expiry_date": None,
            "specialization": "Nội tiết",
            "sub_specializations": ["A", "B"],
            "education": [],
            "experience_years": 5,
            "training_institutions": [],
            "employment_type": "full_time",
            "hire_date": date(2020, 1, 15),
            "contract_end_date": None,
            "is_accepting_new_patients": True,
            "created_at": datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
            "updated_at": datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
        }
        formatted = format_doctor_row(row)
        out = build_csv(columns, labels, [formatted])

        # BOM đầu.
        assert out.startswith("\ufeff")
        # Header có chứa label tiếng Việt + key EN.
        first_line = out.split("\r\n", 1)[0].lstrip("\ufeff")
        assert "Họ tên (full_name)" in first_line
        assert "Giới tính (gender)" in first_line
        assert "Đang hoạt động (is_active)" in first_line
        # Không chứa avatar vì đã bỏ.
        assert "avatar" not in first_line.lower()

        # Body: gender Nữ, datetime theo dd/mm/yyyy HH:MM, bool là "Có".
        body = out.split("\r\n", 1)[1]
        assert "07/03/1985" in body
        assert "Nữ" in body
        assert "A; B" in body
        assert "Toàn thời gian" in body
        assert "01/01/2024 12:00" in body
        # Các ô không có dữ liệu vẫn là chuỗi rỗng, không phải "None".
        assert '"None"' not in body
        # Kết thúc bằng CRLF (RFC 4180).
        assert out.endswith("\r\n")
