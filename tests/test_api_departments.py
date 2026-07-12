"""Unit + integration test cho controller Department.

Phủ các endpoint CRUD + 2 endpoint mới `/{id}` và `/{id}/doctors`
(xem docs/FE_DEPARTMENT_DETAIL.md).
"""
from unittest.mock import MagicMock

import pytest

from app.api.v1 import departments as dept_module


# ==========================================================================
# Pure helpers (không cần app context)
# ==========================================================================

class TestDeriveQualification:
    def test_split_on_comma(self):
        assert dept_module._derive_qualification("Thạc sĩ, Bác sĩ CKI") == "Thạc sĩ"

    def test_no_comma_returns_trimmed(self):
        assert dept_module._derive_qualification("Bác sĩ") == "Bác sĩ"

    def test_none(self):
        assert dept_module._derive_qualification(None) is None

    def test_empty_string(self):
        assert dept_module._derive_qualification("") is None

    def test_strips_spaces(self):
        assert dept_module._derive_qualification("  Tiến sĩ  , Giáo sư") == "Tiến sĩ"


class TestDeriveExperienceDisplay:
    def test_years(self):
        assert dept_module._derive_experience_display(12) == "12 năm"

    def test_zero(self):
        assert dept_module._derive_experience_display(0) == "0 năm"

    def test_none(self):
        assert dept_module._derive_experience_display(None) is None


class TestDeriveSchedule:
    def test_no_schedules_returns_none(self):
        doctor = MagicMock()
        doctor.schedules.filter_by.return_value.order_by.return_value.all.return_value = []
        assert dept_module._derive_schedule(doctor) is None

    def test_sang_only(self):
        from datetime import time

        s = MagicMock()
        s.day_of_week = 1  # T2
        s.start_time = time(8, 0)
        doctor = MagicMock()
        doctor.schedules.filter_by.return_value.order_by.return_value.all.return_value = [s]
        out = dept_module._derive_schedule(doctor)
        assert out["days"] == ["T2"]
        assert out["period"] == "Sáng"
        assert out["summary"] == "T2 (Sáng)"

    def test_mixed_sang_chieu_yields_ca_ngay(self):
        from datetime import time

        s1 = MagicMock()
        s1.day_of_week = 1  # T2
        s1.start_time = time(8, 0)
        s2 = MagicMock()
        s2.day_of_week = 1  # T2
        s2.start_time = time(13, 0)
        doctor = MagicMock()
        doctor.schedules.filter_by.return_value.order_by.return_value.all.return_value = [s1, s2]
        out = dept_module._derive_schedule(doctor)
        assert out["period"] == "Cả ngày"

    def test_multiple_days_sorted(self):
        from datetime import time

        s1 = MagicMock()
        s1.day_of_week = 3  # T4
        s1.start_time = time(8, 0)
        s2 = MagicMock()
        s2.day_of_week = 1  # T2
        s2.start_time = time(8, 0)
        doctor = MagicMock()
        doctor.schedules.filter_by.return_value.order_by.return_value.all.return_value = [s1, s2]
        out = dept_module._derive_schedule(doctor)
        assert out["days"] == ["T2", "T4"]

    def test_unknown_dow_is_dropped(self):
        from datetime import time

        s = MagicMock()
        s.day_of_week = 99  # ngoài 0..6
        s.start_time = time(8, 0)
        doctor = MagicMock()
        doctor.schedules.filter_by.return_value.order_by.return_value.all.return_value = [s]
        out = dept_module._derive_schedule(doctor)
        assert out["days"] == []


# ==========================================================================
# serialize_doctor_summary — không touch DB (mock Appointment query).
# ==========================================================================

class TestSerializeDoctorSummary:
    def test_includes_all_required_fields(self, app):
        doctor = MagicMock()
        doctor.id = 1
        doctor.full_name = "Trần Thị Minh"
        doctor.title = "Thạc sĩ, Bác sĩ CKI"
        doctor.experience_years = 12
        doctor.is_accepting_new_patients = True
        doctor._get_avatar_url.return_value = "https://r2.test/x.png"
        doctor.schedules.filter_by.return_value.order_by.return_value.all.return_value = []

        with app.app_context():
            from app.models.appointment import Appointment

            fake_query = MagicMock(
                with_entities=MagicMock(
                    return_value=MagicMock(
                        filter=MagicMock(
                            return_value=MagicMock(
                                filter=MagicMock(
                                    return_value=MagicMock(
                                        filter=MagicMock(
                                            return_value=MagicMock(
                                                limit=MagicMock(
                                                    return_value=MagicMock(
                                                        count=MagicMock(return_value=0)
                                                    )
                                                )
                                            )
                                        )
                                    )
                                )
                            )
                        )
                    )
                )
            )
            with pytest.MonkeyPatch.context() as m:
                m.setattr(Appointment, "query", fake_query)
                out = dept_module.serialize_doctor_summary(doctor)

        assert out["id"] == 1
        assert out["full_name"] == "Trần Thị Minh"
        assert out["title"] == "Thạc sĩ, Bác sĩ CKI"
        assert out["qualification"] == "Thạc sĩ"
        assert out["experience_years"] == 12
        assert out["experience_display"] == "12 năm"
        assert out["status"] == "available"
        assert out["status_label"] == "ĐANG LÀM VIỆC"
        assert out["avatar_url"] == "https://r2.test/x.png"
        assert out["is_accepting_new_patients"] is True
        assert out["schedule"] is None

    def test_in_session_status_when_appointment_today(self, app):
        doctor = MagicMock()
        doctor.id = 2
        doctor.full_name = "Nguyễn Văn B"
        doctor.title = "Bác sĩ"
        doctor.experience_years = None
        doctor.is_accepting_new_patients = False
        doctor._get_avatar_url.return_value = None
        doctor.schedules.filter_by.return_value.order_by.return_value.all.return_value = []

        with app.app_context():
            from app.models.appointment import Appointment

            fake_query = MagicMock(
                with_entities=MagicMock(
                    return_value=MagicMock(
                        filter=MagicMock(
                            return_value=MagicMock(
                                filter=MagicMock(
                                    return_value=MagicMock(
                                        filter=MagicMock(
                                            return_value=MagicMock(
                                                limit=MagicMock(
                                                    return_value=MagicMock(
                                                        count=MagicMock(return_value=2)
                                                    )
                                                )
                                            )
                                        )
                                    )
                                )
                            )
                        )
                    )
                )
            )
            with pytest.MonkeyPatch.context() as m:
                m.setattr(Appointment, "query", fake_query)
                out = dept_module.serialize_doctor_summary(doctor)

        assert out["status"] == "in_session"
        assert out["status_label"] == "CÓ LỊCH HẸN"
        assert out["experience_display"] is None
        assert out["is_accepting_new_patients"] is False


# ==========================================================================
# API integration — get_department, list_department_doctors
# ==========================================================================

@pytest.fixture()
def patch_dept_service(monkeypatch):
    """Patch `_service` của module departments thành MagicMock."""
    fake_service = MagicMock()
    monkeypatch.setattr(dept_module, "_service", fake_service)
    return fake_service


def test_get_department_api_success(client, db_sqlite, monkeypatch,
                                    make_role, make_user, auth_header,
                                    patch_dept_service):
    dept = MagicMock()
    dept.to_dict.return_value = {
        "id": 1, "code": "CK-001", "name": "Khoa Tim mạch",
        "is_active": True, "head_doctor": {"id": 5, "full_name": "BS A"},
    }
    patch_dept_service.get_department.return_value = dept

    role = make_role("admin", ["department:manage"])
    user = make_user(email="admin@test.local", roles=[role])
    headers = auth_header(user)

    res = client.get("/api/v1/departments/1", headers=headers)
    assert res.status_code == 200
    body = res.get_json()
    assert body["status"] == "success"
    assert body["data"]["id"] == 1
    assert body["data"]["head_doctor"]["id"] == 5
    patch_dept_service.get_department.assert_called_once_with(1)


def test_get_department_api_404(client, db_sqlite, monkeypatch,
                                make_role, make_user, auth_header,
                                patch_dept_service):
    from app.errors import NotFoundException

    patch_dept_service.get_department.side_effect = NotFoundException(
        "errors.department_not_found"
    )

    role = make_role("admin", ["department:manage"])
    user = make_user(email="admin@test.local", roles=[role])
    headers = auth_header(user)

    res = client.get("/api/v1/departments/999", headers=headers)
    assert res.status_code == 404


def test_get_department_api_requires_permission(client, db_sqlite,
                                               monkeypatch,
                                               make_role, make_user,
                                               auth_header):
    # User thiếu permission department:manage -> 403
    role = make_role("user", [])
    user = make_user(email="plain@test.local", roles=[role])
    headers = auth_header(user)

    res = client.get("/api/v1/departments/1", headers=headers)
    assert res.status_code == 403


def test_list_department_doctors_api_success(client, db_sqlite, monkeypatch,
                                             make_role, make_user, auth_header,
                                             patch_dept_service):
    # Tránh query thật vào bảng appointments (không có trong SQLite-safe set).
    monkeypatch.setattr(dept_module, "_count_today_in_session",
                        lambda doctor_id: 0)

    doctor = MagicMock()
    doctor.id = 1
    doctor.full_name = "Trần Thị Minh"
    doctor.title = "Thạc sĩ, Bác sĩ CKI"
    doctor.experience_years = 12
    doctor.is_accepting_new_patients = True
    doctor._get_avatar_url.return_value = "https://r2.test/x.png"
    doctor.schedules.filter_by.return_value.order_by.return_value.all.return_value = []

    patch_dept_service.list_department_doctors.return_value = {
        "stats": {
            "total_doctors": 12, "active_doctors": 10,
            "inactive_doctors": 2, "treating_patients": 47,
        },
        "doctors": [doctor],
        "total": 12,
    }

    role = make_role("admin", ["department:manage"])
    user = make_user(email="admin@test.local", roles=[role])
    headers = auth_header(user)

    res = client.get("/api/v1/departments/1/doctors?page=1&size=10",
                     headers=headers)
    assert res.status_code == 200
    body = res.get_json()
    assert body["status"] == "success"
    assert body["data"]["stats"]["total_doctors"] == 12
    assert body["data"]["stats"]["treating_patients"] == 47
    assert len(body["data"]["doctors"]) == 1
    assert body["data"]["doctors"][0]["full_name"] == "Trần Thị Minh"
    assert body["data"]["doctors"][0]["qualification"] == "Thạc sĩ"
    assert body["meta"]["page"] == 1
    assert body["meta"]["size"] == 10
    assert body["meta"]["totalPage"] == 2  # ceil(12/10)


def test_list_department_doctors_api_passes_filters(client, db_sqlite,
                                                    monkeypatch,
                                                    make_role, make_user,
                                                    auth_header,
                                                    patch_dept_service):
    patch_dept_service.list_department_doctors.return_value = {
        "stats": {"total_doctors": 0, "active_doctors": 0,
                  "inactive_doctors": 0, "treating_patients": 0},
        "doctors": [],
        "total": 0,
    }

    role = make_role("admin", ["department:manage"])
    user = make_user(email="admin@test.local", roles=[role])
    headers = auth_header(user)

    res = client.get(
        "/api/v1/departments/1/doctors?page=2&size=20&q=Nguyen&qualification=Thac%20si",
        headers=headers,
    )
    assert res.status_code == 200
    patch_dept_service.list_department_doctors.assert_called_once_with(
        1, page=2, size=20, q="Nguyen", qualification="Thac si"
    )


def test_list_department_doctors_api_404(client, db_sqlite, monkeypatch,
                                         make_role, make_user, auth_header,
                                         patch_dept_service):
    from app.errors import NotFoundException

    patch_dept_service.list_department_doctors.side_effect = NotFoundException(
        "errors.department_not_found"
    )

    role = make_role("admin", ["department:manage"])
    user = make_user(email="admin@test.local", roles=[role])
    headers = auth_header(user)

    res = client.get("/api/v1/departments/999/doctors", headers=headers)
    assert res.status_code == 404


def test_list_department_doctors_api_size_too_big(client, db_sqlite,
                                                  monkeypatch,
                                                  make_role, make_user,
                                                  auth_header):
    # size > 50 -> 422 (theo spec FE_DEPARTMENT_DETAIL §3.2)
    role = make_role("admin", ["department:manage"])
    user = make_user(email="admin@test.local", roles=[role])
    headers = auth_header(user)

    res = client.get("/api/v1/departments/1/doctors?size=999",
                     headers=headers)
    assert res.status_code == 422


def test_list_department_doctors_api_requires_permission(
    client, db_sqlite, monkeypatch, make_role, make_user, auth_header,
):
    role = make_role("user", [])
    user = make_user(email="plain@test.local", roles=[role])
    headers = auth_header(user)

    res = client.get("/api/v1/departments/1/doctors", headers=headers)
    assert res.status_code == 403


# ==========================================================================
# Export CSV — ?format=csv
# ==========================================================================

class TestExportDoctorsCsv:
    """Test cho GET /api/v1/departments/{id}/doctors?format=csv."""

    def _admin_header(self, make_role, make_user, auth_header):
        role = make_role("admin", ["department:manage"])
        user = make_user(email="admin@test.local", roles=[role])
        return auth_header(user)

    def test_returns_csv_file_with_correct_headers(
        self, client, db_sqlite, monkeypatch,
        make_role, make_user, auth_header, patch_dept_service,
    ):
        from app.models.department import Department

        dept = Department(id=1, code="CK-001", name="Khoa Tim mạch",
                          keywords=[], conditions=[], techniques=[],
                          ai_metadata={}, is_active=True)
        doctor = MagicMock()
        doctor.to_dict.return_value = {
            "id": 1, "full_name": "Trần Thị Minh", "department_id": 1,
            "title": "Thạc sĩ, Bác sĩ CKI", "is_active": True,
            "phone": "0987654321", "email": "minh@example.com",
            "avatar_url": "https://r2.test/x.png",
            "date_of_birth": "1990-05-15", "gender": "female",
            "address": "Hà Nội",
            "license_number": "GD-001", "license_issue_date": "2015-01-01",
            "license_expiry_date": "2030-01-01", "specialization": "Tim mạch",
            "sub_specializations": ["Nội soi tim"], "education": ["ĐH Y Hà Nội"],
            "experience_years": 12, "training_institutions": ["BV Bạch Mai"],
            "employment_type": "full_time", "hire_date": "2020-01-01",
            "contract_end_date": None, "is_accepting_new_patients": True,
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
        patch_dept_service.export_department_doctors_csv.return_value = (
            "\ufeffid,full_name\r\n1,Trần Thị Minh\r\n",
            dept,
            1,
        )

        headers = self._admin_header(make_role, make_user, auth_header)
        res = client.get(
            "/api/v1/departments/1/doctors?format=csv", headers=headers,
        )

        assert res.status_code == 200
        assert res.mimetype == "text/csv"
        assert res.headers.get("Content-Type", "").startswith("text/csv")
        assert "attachment" in res.headers.get("Content-Disposition", "")
        assert "doctors_CK-001_" in res.headers["Content-Disposition"]
        assert res.headers.get("X-Export-Total-Rows") == "1"
        # Body phải có BOM
        assert res.data.decode("utf-8").startswith("\ufeff")

    def test_calls_service_with_query_filters(
        self, client, db_sqlite, monkeypatch,
        make_role, make_user, auth_header, patch_dept_service,
    ):
        dept = MagicMock()
        dept.code = "CK-002"
        patch_dept_service.export_department_doctors_csv.return_value = (
            "\ufeffid\r\n", dept, 0,
        )

        headers = self._admin_header(make_role, make_user, auth_header)
        res = client.get(
            "/api/v1/departments/1/doctors"
            "?format=csv&q=Nguyen&qualification=Thac%20si",
            headers=headers,
        )
        assert res.status_code == 200
        patch_dept_service.export_department_doctors_csv.assert_called_once_with(
            1, q="Nguyen", qualification="Thac si"
        )

    def test_404_when_department_missing(
        self, client, db_sqlite, monkeypatch,
        make_role, make_user, auth_header, patch_dept_service,
    ):
        from app.errors import NotFoundException

        patch_dept_service.export_department_doctors_csv.side_effect = (
            NotFoundException("errors.department_not_found")
        )

        headers = self._admin_header(make_role, make_user, auth_header)
        res = client.get(
            "/api/v1/departments/999/doctors?format=csv", headers=headers,
        )
        assert res.status_code == 404

    def test_invalid_format_returns_422(
        self, client, db_sqlite, monkeypatch,
        make_role, make_user, auth_header,
    ):
        headers = self._admin_header(make_role, make_user, auth_header)
        res = client.get(
            "/api/v1/departments/1/doctors?format=xlsx", headers=headers,
        )
        assert res.status_code == 422

    def test_requires_permission(
        self, client, db_sqlite, monkeypatch,
        make_role, make_user, auth_header,
    ):
        role = make_role("user", [])
        user = make_user(email="plain@test.local", roles=[role])
        headers = auth_header(user)

        res = client.get(
            "/api/v1/departments/1/doctors?format=csv", headers=headers,
        )
        assert res.status_code == 403

    def test_json_response_unchanged(
        self, client, db_sqlite, monkeypatch,
        make_role, make_user, auth_header, patch_dept_service,
    ):
        # Đảm bảo format=json (mặc định) vẫn hoạt động như cũ.
        monkeypatch.setattr(dept_module, "_count_today_in_session",
                            lambda doctor_id: 0)
        doctor = MagicMock()
        doctor.id = 1
        doctor.full_name = "BS A"
        doctor.title = "Bác sĩ"
        doctor.experience_years = 5
        doctor.is_accepting_new_patients = True
        doctor._get_avatar_url.return_value = None
        doctor.schedules.filter_by.return_value.order_by.return_value.all.return_value = []
        patch_dept_service.list_department_doctors.return_value = {
            "stats": {"total_doctors": 1, "active_doctors": 1,
                      "inactive_doctors": 0, "treating_patients": 0},
            "doctors": [doctor],
            "total": 1,
        }

        headers = self._admin_header(make_role, make_user, auth_header)
        res = client.get(
            "/api/v1/departments/1/doctors?format=json", headers=headers,
        )
        assert res.status_code == 200
        body = res.get_json()
        assert body["status"] == "success"
        assert "doctors" in body["data"]