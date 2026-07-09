"""Unit test cho DoctorService - phần CRUD và validation.

Phủ các case:
- Tạo bác sĩ (create_doctor)
- Lấy chi tiết bác sĩ (get_doctor)
- Cập nhật bác sĩ (update_doctor)
- Xóa bác sĩ (delete_doctor)
- Tìm kiếm bác sĩ (search_doctors)
- Giấy phép sắp hết hạn (get_expiring_licenses)
"""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.common.roles import Role
from app.errors import ForbiddenException, NotFoundException, ValidationException
from app.services.doctor_service import DoctorService


def _user(has_roles=()):
    u = MagicMock()
    u.id = 7
    u.has_role = lambda *names: bool(set(has_roles) & set(names))
    return u


def _doctor(id=1, department_id=1, **kwargs):
    d = MagicMock()
    d.id = id
    d.department_id = department_id
    d.full_name = kwargs.get("full_name", f"Doctor {id}")
    d.license_number = kwargs.get("license_number")
    d.is_active = kwargs.get("is_active", True)
    for k, v in kwargs.items():
        setattr(d, k, v)
    return d


def _department(id=1, name="Khoa Test"):
    dept = MagicMock()
    dept.id = id
    dept.name = name
    return dept


def _make_doctor_service(doctor_repo=None, department_repo=None, role_repo=None, statistics_repo=None):
    """Tạo DoctorService với các repo được mock."""
    if doctor_repo is None:
        doctor_repo = MagicMock()
    if department_repo is None:
        department_repo = MagicMock()
    if role_repo is None:
        role_repo = MagicMock()
    if statistics_repo is None:
        statistics_repo = MagicMock()

    svc = DoctorService(
        doctor_repository=doctor_repo,
        department_repository=department_repo,
        role_repository=role_repo,
        statistics_repository=statistics_repo,
    )
    return svc, doctor_repo, department_repo, role_repo, statistics_repo


class TestCreateDoctor:
    def test_admin_can_create_doctor(self):
        doctor_repo = MagicMock()
        department_repo = MagicMock()
        statistics_repo = MagicMock()

        dept = _department()
        department_repo.find_by_id.return_value = dept
        doctor_repo.find_by_license_number.return_value = None
        doctor_repo.add.return_value = _doctor(id=1, full_name="Dr. John Doe")
        statistics_repo.find_or_create.return_value = MagicMock()

        svc = DoctorService(
            doctor_repository=doctor_repo,
            department_repository=department_repo,
            statistics_repository=statistics_repo,
        )

        actor = _user(has_roles=[Role.ADMIN])
        data = {
            "full_name": "Dr. John Doe",
            "department_id": 1,
            "license_number": "GD-12345",
            "specialization": "Cardiology",
        }

        result = svc.create_doctor(actor=actor, data=data)

        assert result.full_name == "Dr. John Doe"
        doctor_repo.add.assert_called_once()

    def test_non_admin_cannot_create(self):
        svc, *_ = _make_doctor_service()
        actor = _user(has_roles=["doctor"])
        data = {"full_name": "Test", "department_id": 1}

        with pytest.raises(ForbiddenException):
            svc.create_doctor(actor=actor, data=data)

    def test_create_with_invalid_department_raises(self):
        doctor_repo = MagicMock()
        department_repo = MagicMock()
        department_repo.find_by_id.return_value = None

        svc = DoctorService(
            doctor_repository=doctor_repo,
            department_repository=department_repo,
        )

        actor = _user(has_roles=[Role.ADMIN])
        data = {"full_name": "Test", "department_id": 999}

        with pytest.raises(ValidationException):
            svc.create_doctor(actor=actor, data=data)

    def test_create_with_duplicate_license_raises(self):
        doctor_repo = MagicMock()
        department_repo = MagicMock()

        department_repo.find_by_id.return_value = _department()
        doctor_repo.find_by_license_number.return_value = _doctor(id=2, license_number="GD-12345")

        svc = DoctorService(
            doctor_repository=doctor_repo,
            department_repository=department_repo,
        )

        actor = _user(has_roles=[Role.ADMIN])
        data = {"full_name": "Test", "department_id": 1, "license_number": "GD-12345"}

        with pytest.raises(ValidationException):
            svc.create_doctor(actor=actor, data=data)


class TestGetDoctor:
    def test_admin_can_get_any_doctor(self):
        doctor_repo = MagicMock()
        doctor_repo.find_by_id.return_value = _doctor(id=5)

        svc = DoctorService(doctor_repository=doctor_repo)

        actor = _user(has_roles=[Role.ADMIN])
        result = svc.get_doctor(actor=actor, doctor_id=5)

        assert result.id == 5

    def test_get_nonexistent_doctor_raises(self):
        doctor_repo = MagicMock()
        doctor_repo.find_by_id.return_value = None

        svc = DoctorService(doctor_repository=doctor_repo)

        actor = _user(has_roles=[Role.ADMIN])
        with pytest.raises(NotFoundException):
            svc.get_doctor(actor=actor, doctor_id=999)

    def test_dept_head_cannot_get_other_dept_doctor(self):
        doctor_repo = MagicMock()
        department_repo = MagicMock()

        dept = _department(id=1)
        department_repo.find_by_head_doctor_id.return_value = dept
        doctor_repo.find_by_id.return_value = _doctor(id=5, department_id=99)

        svc = DoctorService(
            doctor_repository=doctor_repo,
            department_repository=department_repo,
        )

        actor = _user(has_roles=[Role.DEPARTMENT_HEAD])
        with pytest.raises(ForbiddenException):
            svc.get_doctor(actor=actor, doctor_id=5)


class TestUpdateDoctor:
    def test_admin_can_update_doctor(self):
        doctor_repo = MagicMock()
        doctor = _doctor(id=1, full_name="Old Name")
        doctor_repo.find_by_id.return_value = doctor
        doctor_repo.find_by_license_number.return_value = None
        doctor_repo.update.return_value = doctor

        svc = DoctorService(doctor_repository=doctor_repo)

        actor = _user(has_roles=[Role.ADMIN])
        data = {"full_name": "New Name"}

        result = svc.update_doctor(actor=actor, doctor_id=1, data=data)

        doctor_repo.update.assert_called_once()

    def test_dept_head_can_update_own_dept_doctor(self):
        doctor_repo = MagicMock()
        department_repo = MagicMock()

        dept = _department(id=1)
        department_repo.find_by_head_doctor_id.return_value = dept
        doctor = _doctor(id=1, department_id=1, full_name="Old")
        doctor_repo.find_by_id.return_value = doctor
        doctor_repo.update.return_value = doctor

        svc = DoctorService(
            doctor_repository=doctor_repo,
            department_repository=department_repo,
        )

        actor = _user(has_roles=[Role.DEPARTMENT_HEAD])
        data = {"title": "Phó khoa"}

        result = svc.update_doctor(actor=actor, doctor_id=1, data=data)

        doctor_repo.update.assert_called_once()

    def test_dept_head_cannot_update_other_dept_doctor(self):
        doctor_repo = MagicMock()
        department_repo = MagicMock()

        dept = _department(id=1)
        department_repo.find_by_head_doctor_id.return_value = dept
        doctor = _doctor(id=5, department_id=99)
        doctor_repo.find_by_id.return_value = doctor

        svc = DoctorService(
            doctor_repository=doctor_repo,
            department_repository=department_repo,
        )

        actor = _user(has_roles=[Role.DEPARTMENT_HEAD])
        data = {"title": "Trưởng khoa"}

        with pytest.raises(ForbiddenException):
            svc.update_doctor(actor=actor, doctor_id=5, data=data)

    def test_update_license_number_to_existing_raises(self):
        doctor_repo = MagicMock()
        doctor = _doctor(id=1, license_number=None)
        doctor_repo.find_by_id.return_value = doctor
        doctor_repo.find_by_license_number.return_value = _doctor(id=2, license_number="GD-999")

        svc = DoctorService(doctor_repository=doctor_repo)

        actor = _user(has_roles=[Role.ADMIN])
        data = {"license_number": "GD-999"}

        with pytest.raises(ValidationException):
            svc.update_doctor(actor=actor, doctor_id=1, data=data)

    def test_update_avatar_key_cleans_up_old_r2_object(self):
        doctor_repo = MagicMock()
        doctor = _doctor(id=1, avatar_object_key="doctor/avatar/old.png")
        doctor_repo.find_by_id.return_value = doctor
        doctor_repo.update.return_value = doctor

        svc = DoctorService(doctor_repository=doctor_repo)
        actor = _user(has_roles=[Role.ADMIN])

        with patch.object(svc, "_cleanup_old_avatar") as mock_cleanup:
            svc.update_doctor(
                actor=actor,
                doctor_id=1,
                data={"avatar_object_key": "doctor/avatar/new.png"},
            )
            mock_cleanup.assert_called_once()
            args, _ = mock_cleanup.call_args
            assert args[0] == "doctor/avatar/old.png"
            assert args[1] == "doctor/avatar/new.png"


class TestDeleteDoctor:
    def test_admin_can_soft_delete_doctor(self):
        doctor_repo = MagicMock()
        doctor = _doctor(id=1, is_active=True)
        doctor_repo.find_by_id.return_value = doctor

        svc = DoctorService(doctor_repository=doctor_repo)

        actor = _user(has_roles=[Role.ADMIN])
        with patch.object(svc, "_cleanup_old_avatar") as mock_cleanup:
            svc.delete_doctor(actor=actor, doctor_id=1)
            doctor_repo.delete.assert_called_once()
            mock_cleanup.assert_called_once()

        doctor_repo.delete.assert_called_once()

    def test_non_admin_cannot_delete(self):
        doctor_repo = MagicMock()
        department_repo = MagicMock()
        department_repo.find_by_head_doctor_id.return_value = _department(id=1)

        svc = DoctorService(
            doctor_repository=doctor_repo,
            department_repository=department_repo,
        )

        actor = _user(has_roles=[Role.DEPARTMENT_HEAD])
        with pytest.raises(ForbiddenException):
            svc.delete_doctor(actor=actor, doctor_id=1)


class TestSearchDoctors:
    def test_search_returns_results(self):
        doctor_repo = MagicMock()
        department_repo = MagicMock()

        doctor_repo.search.return_value = ([_doctor(id=1), _doctor(id=2)], 2)

        svc = DoctorService(
            doctor_repository=doctor_repo,
            department_repository=department_repo,
        )

        actor = _user(has_roles=[Role.ADMIN])
        items, total = svc.search_doctors(
            actor=actor, keyword="cardio", page=1, size=20
        )

        doctor_repo.search.assert_called_once_with("cardio", 1, 20, department_id=None)
        assert total == 2

    def test_dept_head_search_limited_to_own_dept(self):
        doctor_repo = MagicMock()
        department_repo = MagicMock()

        dept = _department(id=5)
        department_repo.find_by_head_doctor_id.return_value = dept
        doctor_repo.search.return_value = ([], 0)

        svc = DoctorService(
            doctor_repository=doctor_repo,
            department_repository=department_repo,
        )

        actor = _user(has_roles=[Role.DEPARTMENT_HEAD])
        items, total = svc.search_doctors(
            actor=actor, keyword="test", page=1, size=20
        )

        doctor_repo.search.assert_called_once_with("test", 1, 20, department_id=5)


class TestExpiringLicenses:
    def test_admin_can_get_expiring_licenses(self):
        doctor_repo = MagicMock()
        doctors = [_doctor(id=1, license_expiry_date=date(2026, 8, 1))]
        doctor_repo.find_expiring_licenses.return_value = doctors

        svc = DoctorService(doctor_repository=doctor_repo)

        actor = _user(has_roles=[Role.ADMIN])
        result = svc.get_expiring_licenses(actor=actor, days=30)

        doctor_repo.find_expiring_licenses.assert_called_once_with(30)
        assert len(result) == 1

    def test_non_admin_cannot_get_expiring_licenses(self):
        svc, *_ = _make_doctor_service()
        actor = _user(has_roles=[Role.DEPARTMENT_HEAD])

        with pytest.raises(ForbiddenException):
            svc.get_expiring_licenses(actor=actor)
