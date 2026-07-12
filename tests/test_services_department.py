"""Unit test cho DepartmentService — phủ logic nghiệp vụ: sinh mã, đổi avatar,
_cleanup_old_avatar, đụng độ mã.

Sau refactor 1a2b3c4d5e6f: bỏ head_doctor_id, bỏ auto-grant role staff, bỏ
scope theo khoa. Test chỉ tập trung vào nghiệp vụ còn lại.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from app.errors import ConflictException, NotFoundException
from app.services.department_service import DepartmentService


# ==========================================================================
# Helpers
# ==========================================================================

def _svc(dept_repo=None):
    """Tạo service với mock department repo (sau refactor chỉ cần 1 repo)."""
    dept_repo = dept_repo or MagicMock()
    return DepartmentService(department_repository=dept_repo), dept_repo


def _make_existing(**attrs):
    """Mock một Department instance với các thuộc tính mặc định cần thiết."""
    existing = MagicMock()
    existing.is_active = False
    existing.avatar_object_key = None
    existing.avatar_url = None
    for k, v in attrs.items():
        setattr(existing, k, v)
    return existing


# ==========================================================================
# list_departments / get_stats
# ==========================================================================

class TestListDepartments:
    def test_calls_paginate(self):
        svc, d = _svc()
        d.paginate.return_value = ([MagicMock(), MagicMock()], 2)
        items, total = svc.list_departments(page=2, size=5)
        d.paginate.assert_called_once_with(2, 5)
        assert total == 2
        assert len(items) == 2


class TestGetStats:
    def test_returns_counts(self):
        svc, d = _svc()
        d.count_by_status.return_value = (10, 6, 4)
        result = svc.get_stats()
        assert result == {"total": 10, "active": 6, "inactive": 4}


# ==========================================================================
# create_department
# ==========================================================================

class TestCreateDepartment:
    def test_basic_create_with_auto_code(self):
        svc, d = _svc()
        d.max_code_number.return_value = 2
        result = svc.create_department(name="Khoa Nội")
        d.add.assert_called_once()
        d.commit.assert_called_once()
        assert result.code == "CK-003"
        assert result.name == "Khoa Nội"

    def test_default_inactive_when_no_flag(self):
        # Sau refactor: không có head_doctor, is_active mặc định False. Tạo vẫn OK.
        svc, d = _svc()
        d.max_code_number.return_value = 0
        result = svc.create_department(name="Khoa")
        assert result.is_active is False

    def test_active_allowed_without_head(self):
        # Sau refactor: is_active=true không cần head_doctor_id. Tạo OK.
        svc, d = _svc()
        d.max_code_number.return_value = 0
        result = svc.create_department(name="Khoa", is_active=True)
        assert result.is_active is True

    def test_code_collision_retries_and_succeeds(self):
        svc, d = _svc()
        d.max_code_number.side_effect = [5, 6]

        # Lần commit đầu raise IntegrityError, lần 2 OK.
        d.commit.side_effect = [IntegrityError("x", {}, {}), None]

        result = svc.create_department(name="Khoa")
        assert result.code == "CK-007"  # 6+1
        assert d.rollback.call_count == 1

    def test_code_collision_exhausted_raises_conflict(self):
        svc, d = _svc()
        d.max_code_number.return_value = 10
        d.commit.side_effect = IntegrityError("x", {}, {})

        with pytest.raises(ConflictException):
            svc.create_department(name="Khoa")
        assert d.rollback.call_count >= 1

    def test_keywords_conditions_defaults(self):
        svc, d = _svc()
        d.max_code_number.return_value = 0
        result = svc.create_department(name="Khoa", keywords=None)
        assert result.keywords == []
        assert result.conditions == []
        assert result.ai_metadata == {}


# ==========================================================================
# update_department
# ==========================================================================

class TestUpdateDepartment:
    def test_not_found_raises(self):
        svc, d = _svc()
        d.find_by_id.return_value = None
        with pytest.raises(NotFoundException):
            svc.update_department(99, name="x")

    def test_update_name(self):
        svc, d = _svc()
        existing = _make_existing(is_active=True, avatar_url="old")
        d.find_by_id.return_value = existing

        result = svc.update_department(1, name="Mới")
        assert existing.name == "Mới"
        d.commit.assert_called_once()
        assert result is existing

    def test_update_is_active(self):
        # Sau refactor: FE có thể bật/tắt khoa trực tiếp qua is_active.
        svc, d = _svc()
        existing = _make_existing(is_active=False)
        d.find_by_id.return_value = existing

        svc.update_department(1, is_active=True)
        assert existing.is_active is True

    def test_update_location(self):
        svc, d = _svc()
        existing = _make_existing(is_active=True)
        d.find_by_id.return_value = existing
        svc.update_department(1, location="Tầng 9")
        assert existing.location == "Tầng 9"

    def test_update_avatar_object_key_clears_cached_url(self):
        svc, d = _svc()
        existing = _make_existing(
            is_active=True, avatar_object_key="old.png", avatar_url="https://cached/url"
        )
        d.find_by_id.return_value = existing

        svc.update_department(1, avatar_object_key="new.png")
        assert existing.avatar_object_key == "new.png"
        assert existing.avatar_url is None  # cache bị xoá

    def test_update_arrays_and_metadata(self):
        svc, d = _svc()
        existing = _make_existing(is_active=True)
        d.find_by_id.return_value = existing

        svc.update_department(
            1,
            keywords=["k1", "k2"],
            conditions=["c1"],
            techniques=["t1"],
            ai_metadata={"icd10": ["A01"]},
            description="d",
            avatar_url="https://new/url",
        )
        assert existing.keywords == ["k1", "k2"]
        assert existing.conditions == ["c1"]
        assert existing.techniques == ["t1"]
        assert existing.ai_metadata == {"icd10": ["A01"]}
        assert existing.description == "d"
        assert existing.avatar_url == "https://new/url"


# ==========================================================================
# _cleanup_old_avatar (private nhưng quan trọng)
# ==========================================================================

class TestCleanupOldAvatar:
    def test_old_key_none_does_nothing(self):
        svc, _ = _svc()
        with patch("app.services.storage.delete_object") as d:
            svc._cleanup_old_avatar(None, "new")
            d.assert_not_called()

    def test_same_key_does_nothing(self):
        svc, _ = _svc()
        with patch("app.services.storage.delete_object") as d:
            svc._cleanup_old_avatar("k", "k")
            d.assert_not_called()

    def test_delete_old_key(self):
        svc, _ = _svc()
        with patch("app.services.storage.delete_object") as d:
            svc._cleanup_old_avatar("old", "new")
            d.assert_called_once_with("old")

    def test_delete_failure_logged_not_raised(self):
        svc, _ = _svc()
        from botocore.exceptions import BotoCoreError

        with patch(
            "app.services.storage.delete_object",
            side_effect=BotoCoreError(),
        ):
            # Không raise.
            svc._cleanup_old_avatar("old", "new")


# ==========================================================================
# _next_code
# ==========================================================================

class TestNextCode:
    def test_format_three_digits(self):
        svc, d = _svc()
        d.max_code_number.return_value = 8
        assert svc._next_code() == "CK-009"

    def test_format_pads_to_three(self):
        svc, d = _svc()
        d.max_code_number.return_value = 41
        assert svc._next_code() == "CK-042"

    def test_starts_at_001_when_empty(self):
        svc, d = _svc()
        d.max_code_number.return_value = 0
        assert svc._next_code() == "CK-001"


# ==========================================================================
# get_department (FE_DEPARTMENT_DETAIL)
# ==========================================================================

class TestGetDepartment:
    def test_returns_department_when_found(self):
        svc, d = _svc()
        dept = MagicMock()
        d.find_by_id.return_value = dept

        result = svc.get_department(7)
        assert result is dept
        d.find_by_id.assert_called_once_with(7)

    def test_raises_404_when_missing(self):
        svc, d = _svc()
        d.find_by_id.return_value = None
        with pytest.raises(NotFoundException):
            svc.get_department(999)


# ==========================================================================
# list_department_doctors (compound endpoint)
# ==========================================================================

class TestListDepartmentDoctors:
    def _mock_doctor(self, doctor_id=1, full_name="BS A", title="Thạc sĩ",
                     experience_years=10, is_active=True,
                     avatar_url="https://r2.test/a.png"):
        d = MagicMock()
        d.id = doctor_id
        d.full_name = full_name
        d.title = title
        d.experience_years = experience_years
        d.is_active = is_active
        d._get_avatar_url.return_value = avatar_url
        d.is_accepting_new_patients = True
        d.schedules.filter_by.return_value.order_by.return_value.all.return_value = []
        return d

    def test_404_when_department_missing(self):
        svc, d = _svc()
        d.find_by_id.return_value = None
        with pytest.raises(NotFoundException):
            svc.list_department_doctors(99)

    def test_compound_returns_stats_and_doctors(self):
        svc, d = _svc()
        d.find_by_id.return_value = MagicMock()
        d.doctor_stats_by_status.return_value = (12, 10)
        d.treating_patients_today.return_value = 47
        doctor = self._mock_doctor()
        d.list_doctors_for_department.return_value = ([doctor], 12)

        result = svc.list_department_doctors(1, page=1, size=10)

        assert result["stats"] == {
            "total_doctors": 12,
            "active_doctors": 10,
            "inactive_doctors": 2,
            "treating_patients": 47,
        }
        assert result["doctors"] == [doctor]
        assert result["total"] == 12
        # Stats + list đều được gọi với đúng department_id.
        d.doctor_stats_by_status.assert_called_once_with(1)
        d.treating_patients_today.assert_called_once_with(1)
        d.list_doctors_for_department.assert_called_once_with(
            1, page=1, size=10, q=None, qualification=None
        )

    def test_inactive_count_clamped_at_zero(self):
        # Phòng trường hợp active > total (do data bất thường) -> không âm.
        svc, d = _svc()
        d.find_by_id.return_value = MagicMock()
        d.doctor_stats_by_status.return_value = (5, 6)  # lỗi data
        d.treating_patients_today.return_value = 0
        d.list_doctors_for_department.return_value = ([], 5)

        result = svc.list_department_doctors(1)
        assert result["stats"]["inactive_doctors"] == 0
        assert result["stats"]["active_doctors"] == 6

    def test_passes_filters_to_repository(self):
        svc, d = _svc()
        d.find_by_id.return_value = MagicMock()
        d.doctor_stats_by_status.return_value = (0, 0)
        d.treating_patients_today.return_value = 0
        d.list_doctors_for_department.return_value = ([], 0)

        svc.list_department_doctors(1, page=2, size=25, q="Nguyễn",
                                    qualification="Thạc sĩ")
        d.list_doctors_for_department.assert_called_once_with(
            1, page=2, size=25, q="Nguyễn", qualification="Thạc sĩ"
        )


# ==========================================================================
# export_department_doctors_csv
# ==========================================================================

class TestExportDepartmentDoctorsCsv:
    def _mock_doctor_dict(self, **overrides):
        base = {
            "id": 1, "full_name": "Trần Thị Minh", "department_id": 1,
            "title": "Thạc sĩ, Bác sĩ CKI", "is_active": True,
            "phone": "0987654321", "email": "minh@example.com",
            "avatar_url": "https://r2.test/x.png",
            "date_of_birth": "1990-05-15", "gender": "female",
            "address": "Hà Nội",
            "license_number": "GD-001", "license_issue_date": "2015-01-01",
            "license_expiry_date": "2030-01-01", "specialization": "Tim mạch",
            "sub_specializations": ["Nội soi tim"],
            "education": ["ĐH Y Hà Nội"],
            "experience_years": 12,
            "training_institutions": ["BV Bạch Mai"],
            "employment_type": "full_time", "hire_date": "2020-01-01",
            "contract_end_date": None,
            "is_accepting_new_patients": True,
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
        base.update(overrides)
        d = MagicMock()
        d.to_dict.return_value = base
        return d

    def test_404_when_department_missing(self):
        svc, d_repo = _svc()
        d_repo.find_by_id.return_value = None
        with pytest.raises(NotFoundException):
            svc.export_department_doctors_csv(999)

    def test_returns_csv_text_department_and_count(self):
        svc, d_repo = _svc()
        dept = MagicMock()
        d_repo.find_by_id.return_value = dept
        doctors = [self._mock_doctor_dict(id=1), self._mock_doctor_dict(id=2)]
        d_repo.list_all_doctors_for_department.return_value = doctors

        csv_text, returned_dept, total = svc.export_department_doctors_csv(1)

        assert returned_dept is dept
        assert total == 2
        # BOM + header label tiếng Việt + 2 dòng dữ liệu.
        assert csv_text.startswith("\ufeff")
        assert "Họ tên (full_name)" in csv_text
        assert "Trần Thị Minh" in csv_text
        # Các field full đều có mặt trong header.
        for col in (
            "Số giấy phép hành nghề (license_number)",
            "Chuyên khoa chính (specialization)",
            "Chuyên khoa phụ (sub_specializations)",
            "Học vấn (education)",
            "Nơi đào tạo (training_institutions)",
            "Đang nhận bệnh nhân mới (is_accepting_new_patients)",
        ):
            assert col in csv_text
        # Bỏ avatar theo yêu cầu nghiệp vụ: header & body KHÔNG chứa avatar.
        assert "avatar_url" not in csv_text.lower()
        assert "avatar" not in csv_text.split("\r\n", 1)[0].lower()

    def test_gender_and_employment_rendered_vietnamese(self):
        svc, d_repo = _svc()
        d_repo.find_by_id.return_value = MagicMock()
        doctors = [self._mock_doctor_dict(gender="female", employment_type="full_time")]
        d_repo.list_all_doctors_for_department.return_value = doctors

        csv_text, _, _ = svc.export_department_doctors_csv(1)
        # Body chứa nhãn tiếng Việt thay vì mã enum thô.
        body_line = csv_text.split("\r\n")[1] if "\r\n" in csv_text else ""
        assert "Nữ" in body_line
        assert "Toàn thời gian" in body_line
        assert "female" not in body_line
        assert "full_time" not in body_line

    def test_bool_rendered_co_khong(self):
        svc, d_repo = _svc()
        d_repo.find_by_id.return_value = MagicMock()
        doctors = [self._mock_doctor_dict(is_active=True, is_accepting_new_patients=False)]
        d_repo.list_all_doctors_for_department.return_value = doctors

        csv_text, _, _ = svc.export_department_doctors_csv(1)
        # Body render "Có"/"Không" thay cho true/false.
        body = csv_text.split("\r\n", 1)[1]
        assert "Có" in body
        assert "Không" in body
        assert "true" not in body
        assert "false" not in body

    def test_passes_filters_to_repository(self):
        svc, d_repo = _svc()
        d_repo.find_by_id.return_value = MagicMock()
        d_repo.list_all_doctors_for_department.return_value = []

        svc.export_department_doctors_csv(1, q="Nguyễn", qualification="TS")

        d_repo.list_all_doctors_for_department.assert_called_once_with(
            1, q="Nguyễn", qualification="TS"
        )

    def test_empty_doctors_returns_header_only(self):
        svc, d_repo = _svc()
        d_repo.find_by_id.return_value = MagicMock()
        d_repo.list_all_doctors_for_department.return_value = []

        csv_text, _, total = svc.export_department_doctors_csv(1)

        assert total == 0
        # Chỉ header, không có dòng dữ liệu.
        assert csv_text.count("\r\n") == 1  # header + CRLF, không có dòng nào khác